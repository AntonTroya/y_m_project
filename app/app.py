from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from yandex_music import Client
from datetime import datetime

#  Настройки приложения: ключ, бд
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['SECRET_KEY'] = 'simple-secret-key-change-me'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# База данных
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    # Настройки для Пользователя: логин, id, ключ
    id = db.Column(db.Integer, primary_key=True)
    yandex_id = db.Column(db.String(100), unique=True)
    username = db.Column(db.String(100))
    login = db.Column(db.String(100))  # Добавляем поле для логина
    token = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Favorite(db.Model):
    # Избранное: треки
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    track_id = db.Column(db.String(100))
    track_title = db.Column(db.String(200))
    track_artist = db.Column(db.String(200))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

class Playlist(db.Model):
    # Плейлисты
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PlaylistTrack(db.Model):
    # Реализация треков в плейлистах
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlist.id'))
    track_id = db.Column(db.String(100))
    track_title = db.Column(db.String(200))
    track_artist = db.Column(db.String(200))

# Авторизация
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Функции для работы с Яндекс музыкой
def get_yandex_client(token):
    # Создание клиента Яндекс Музыки
    try:
        return Client(token).init()
    except Exception as e:
        print(f"Ошибка создания клиента: {e}")
        return None

def search_tracks(client, query):
    # Поиск треков
    try:
        result = client.search(query, type_='track')
        tracks = []
        if result and result.tracks:
            for track in result.tracks.results[:10]:
                tracks.append({
                    'id': track.id,
                    'title': track.title,
                    'artist': track.artists[0].name if track.artists else 'Unknown',
                    'duration': track.duration_ms // 1000 if track.duration_ms else 0
                })
        return tracks
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return []

# Маршруты
@app.route('/')
def index():
    # Главная страница
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    #Авторизация через Яндекс
    if request.method == 'POST':
        try:
            print("\n" + "="*50)
            print("АВТОРИЗАЦИЯ В ЯНДЕКС МУЗЫКЕ")
            print("="*50)
            
            # Создаем клиент для авторизации
            client = Client()
            
            def on_code(code):
                print(f"🔑 ВАШ КОД: {code.user_code}")
                print(f"🔗 Ссылка: {code.verification_url}")
                print("\n👉 1. Откройте ссылку в браузере")
                print(f"👉 2. Введите код: {code.user_code}")
                print("👉 3. Подтвердите вход")
                print("="*50 + "\n")
            
            # Получение токена через устройство
            token_response = client.device_auth(on_code=on_code)
            
            # Создание клиента с полученным токеном
            client_with_token = Client(token_response.access_token).init()
            
            # Получение информации об аккаунте
            account = client_with_token.account_status()
            
            # Получение ID и логина пользователя
            yandex_id = str(getattr(account, 'id', getattr(account, 'uid', None)))
            user_login = getattr(account, 'login', None)
            
            # Получение логина из полей, если он не найден
            if not user_login:
                user_login = getattr(account, 'display_name', getattr(account, 'name', 'user'))
            
            # Использование ID, если он не найден - дополнительно
            if not user_login:
                user_login = f"user_{yandex_id[:8]}"
            
            print(f"✅ Получен логин: {user_login}")
            print(f"✅ Yandex ID: {yandex_id}")
            
            # Поиск или создание пользователя
            user = User.query.filter_by(yandex_id=yandex_id).first()
            if not user:
                user = User(
                    yandex_id=yandex_id,
                    login=user_login,
                    username=user_login,  # Для совместимости
                    token=token_response.access_token
                )
                db.session.add(user)
                db.session.commit()
                print(f"✅ Создан новый пользователь: {user.login}")
            else:
                user.login = user_login
                user.username = user_login
                user.token = token_response.access_token
                db.session.commit()
                print(f"✅ Обновлен токен пользователя: {user.login}")
            
            login_user(user)
            flash(f'Добро пожаловать, {user_login}!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            print(f"❌ Ошибка авторизации: {e}")
            import traceback
            traceback.print_exc()
            flash(f'Ошибка авторизации: {str(e)}', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # Выход
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Панель управления
    favorites = Favorite.query.filter_by(user_id=current_user.id).count()
    playlists = Playlist.query.filter_by(user_id=current_user.id).count()
    
    # Использование login пользователя для отображения
    display_name = current_user.login or current_user.username or "Пользователь"
    
    return render_template('dashboard.html',
                         user=current_user,
                         display_name=display_name,
                         favorites_count=favorites,
                         playlists_count=playlists)

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    # Поиск музыки
    tracks = []
    query = ''
    
    if request.method == 'POST':
        query = request.form.get('query', '')
        if query:
            client = get_yandex_client(current_user.token)
            if client:
                tracks = search_tracks(client, query)
            else:
                flash('Ошибка подключения к Яндекс Музыке', 'danger')
    
    return render_template('search.html', tracks=tracks, query=query)

@app.route('/add-to-favorites', methods=['POST'])
@login_required
def add_to_favorites():
    # Добавление в избранное
    track_id = request.form.get('track_id')
    track_title = request.form.get('track_title')
    track_artist = request.form.get('track_artist')
    
    existing = Favorite.query.filter_by(
        user_id=current_user.id, 
        track_id=track_id
    ).first()
    
    if not existing:
        favorite = Favorite(
            user_id=current_user.id,
            track_id=track_id,
            track_title=track_title,
            track_artist=track_artist
        )
        db.session.add(favorite)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Добавлено в избранное'})
    
    return jsonify({'success': False, 'message': 'Уже в избранном'})

@app.route('/remove-from-favorites', methods=['POST'])
@login_required
def remove_from_favorites():
    # Удаление из избранного
    track_id = request.form.get('track_id')
    favorite = Favorite.query.filter_by(
        user_id=current_user.id, 
        track_id=track_id
    ).first()
    
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False})

@app.route('/favorites')
@login_required
def favorites():
    # Страница избранное
    favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    return render_template('favorites.html', favorites=favorites)

@app.route('/create-playlist', methods=['POST'])
@login_required
def create_playlist():
    # Создание плейлистов
    name = request.form.get('name')
    if name:
        playlist = Playlist(user_id=current_user.id, name=name)
        db.session.add(playlist)
        db.session.commit()
        return jsonify({'success': True, 'playlist_id': playlist.id})
    return jsonify({'success': False})

@app.route('/playlists')
@login_required
def playlists():
    # Список плейлистов
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    return render_template('playlists.html', playlists=playlists)

@app.route('/playlist/<int:playlist_id>')
@login_required
def playlist_detail(playlist_id):
    # Плейлист - детали
    playlist = Playlist.query.get_or_404(playlist_id)
    if playlist.user_id != current_user.id:
        flash('Нет доступа', 'danger')
        return redirect(url_for('playlists'))
    
    tracks = PlaylistTrack.query.filter_by(playlist_id=playlist_id).all()
    return render_template('playlist_detail.html', playlist=playlist, tracks=tracks)

@app.route('/add-to-playlist', methods=['POST'])
@login_required
def add_to_playlist():
    # Добавление трека в плейлист
    playlist_id = request.form.get('playlist_id')
    track_id = request.form.get('track_id')
    track_title = request.form.get('track_title')
    track_artist = request.form.get('track_artist')
    
    existing = PlaylistTrack.query.filter_by(
        playlist_id=playlist_id,
        track_id=track_id
    ).first()
    
    if not existing:
        track = PlaylistTrack(
            playlist_id=playlist_id,
            track_id=track_id,
            track_title=track_title,
            track_artist=track_artist
        )
        db.session.add(track)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Трек уже в плейлисте'})

@app.route('/api/playlists')
@login_required
def api_playlists():
    # API для получения списка плейлистов
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    return jsonify([{'id': p.id, 'name': p.name} for p in playlists])

# Запуск
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("\n" + "="*50)
    print("🎵 YANDEX MUSIC PLAYER ЗАПУЩЕН")
    print("="*50)
    print("🌐 Откройте в браузере: http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)

    

    