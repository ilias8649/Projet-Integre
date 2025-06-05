from flask import Flask, render_template, redirect, request, session
import os
import requests
from anilist_api import get_user_profile, get_watched_titles, add_anime_to_watchlist, get_anime_metadata, get_full_user_stats, get_top_rated_favourites, get_score_distribution, get_format_status_country_distributions
from llm_engine import generate_recommendations, start_clarification_conversation, continue_clarification_conversation, generate_refined_recommendations
from calendar_integration import start_google_auth, handle_google_callback, insert_calendar_event, get_upcoming_events, get_calendar_stats
from functools import wraps


app = Flask(__name__)
app.secret_key = os.urandom(24)

CLIENT_ID = 'your_anilist_client_id_here'
CLIENT_SECRET = 'your_anilist_client_secret_here'
REDIRECT_URI = 'http://localhost:5000/callback'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('username'):
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return redirect(f"https://anilist.co/api/v2/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_url = "https://anilist.co/api/v2/oauth/token"
    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'code': code
    }
    response = requests.post(token_url, data=payload)
    token_data = response.json()
    session['access_token'] = token_data.get('access_token')

    
    user_info = get_user_profile(session['access_token'])
    session['username'] = user_info.get('name')
    session['avatar'] = user_info.get('avatar', '')

    
    return redirect('/')

@app.route('/recommend', methods=['GET', 'POST'])
@login_required
def recommend():
    token = session.get('access_token')
    user_info = get_user_profile(token)
    seen_titles = get_watched_titles(token, user_info["name"])

    message = session.pop('message', None)

    
    if request.method == 'POST' or 'recommendations' in session:
        if 'recommendations' not in session:
            llm_response = generate_recommendations(user_info, seen_titles)
            import re
            recommendations = []
            if isinstance(llm_response, str) and "Raisonnement" in llm_response and "Titre" in llm_response:
                blocks = re.split(r'\n?-{3,}\n?', llm_response)
                for block in blocks:
                    if "Titre" in block:
                        champ = {}
                        for line in block.splitlines():
                            if line.lower().startswith("raisonnement :"):
                                champ["raisonnement"] = line.split(":", 1)[1].strip()
                            elif line.lower().startswith("titre :"):
                                champ["titre"] = line.split(":", 1)[1].strip()
                            elif line.lower().startswith("description :"):
                                champ["description"] = line.split(":", 1)[1].strip()
                            elif line.lower().startswith("pourquoi :"):
                                champ["pourquoi"] = line.split(":", 1)[1].strip()
                        if champ.get("titre"):
                            meta = get_anime_metadata(token, champ["titre"])
                            champ["episodes"] = meta.get("episodes", 12)
                            champ["duration"] = meta.get("duration", 24)
                            champ["cover"] = meta.get("cover")
                            champ["format"] = meta.get("format", "TV")
                            champ["id"] = meta.get("id")  
                            recommendations.append(champ)
            else:
                recommendations = [{"raisonnement": llm_response, "titre": "", "description": "", "pourquoi": "", "episodes": 1, "duration": 24}]
            session['recommendations'] = recommendations
        else:
            recommendations = session['recommendations']
        return render_template('recommend.html', recommendations=recommendations, message=message)
    else:
        
        return render_template('recommend.html', recommendations=None, message=message)

@app.route('/add_to_watchlist', methods=['POST'])
@login_required
def add_to_watchlist():
    token = session.get('access_token')
    anime_title = request.form.get('anime_title')
    success = add_anime_to_watchlist(token, anime_title)
    if success:
        session['message'] = f"L'animé « {anime_title} » a été ajouté à votre watchlist !"
    else:
        session['message'] = f"Erreur lors de l'ajout de « {anime_title} » à la watchlist."
    return redirect('/recommend')

@app.route('/reset_recommendations', methods=['POST'])
@login_required
def reset_recommendations():
    session.pop('recommendations', None)
    return redirect('/recommend')

@app.route('/calendar')
@login_required
def calendar():
    google_connected = session.get('google_connected', False)
    events = []
    stats = {}
    message = session.pop('message', None) 

    if google_connected:
        events = get_upcoming_events(days_ahead=30) 
        stats = get_calendar_stats()
    
    return render_template('calendar.html', 
                           google_connected=google_connected, 
                           events=events,
                           stats=stats,
                           message=message) 

@app.route('/authorize_gcal')
@login_required
def authorize_gcal():
    return start_google_auth()

@app.route('/gcal_callback')
@login_required
def gcal_callback():
    return handle_google_callback()

@app.route('/schedule_viewing', methods=['POST'])
@login_required
def schedule_viewing():
    anime_title = request.form.get('anime_title')
    start_time = request.form.get('start_time')  
    try:
        num_episodes = int(request.form.get('num_episodes', 1))
        if num_episodes < 1:
            num_episodes = 1
    except ValueError:
        num_episodes = 1

    
    if not start_time:
        session['message'] = "❌ Veuillez sélectionner un créneau horaire valide."
        return redirect('/recommend')

    success = insert_calendar_event(anime_title, num_episodes, start_time)
    if success:
        session['message'] = f"L'animé « {anime_title} » ({num_episodes} épisode(s)) a été planifié dans Google Calendar ✅"
    else:
        session['message'] = f"❌ Impossible de planifier « {anime_title} ». Connecte-toi à Google."
    return redirect('/recommend')

@app.route('/stats')
@login_required
def stats():
    token = session.get('access_token')
    if not token:
        return redirect('/')
    user_info = get_user_profile(token)
    username = user_info['name']
    avatar = user_info.get('avatar')

    stats = get_full_user_stats(token, username)
    favourites = get_top_rated_favourites(token, username)
    score_distribution = get_score_distribution(token, username)
    pie_distributions = get_format_status_country_distributions(token, username)

    return render_template('stats.html',
                           username=username,
                           avatar=avatar,
                           nb_watched=stats["watched"],
                           nb_watching=stats["watching"],
                           nb_planned=stats["planned"],
                           nb_total=stats["total"],
                           nb_dropped=stats["dropped"],
                           avg_episodes=stats["avg_episodes"],
                           completion_pct=stats["completion_pct"],
                           genres=stats["top_genres"],
                           episodes_watched=stats["episodes_watched"],
                           time_spent=stats["time_spent"],
                           favourites=favourites,
                           score_distribution=score_distribution,
                           pie_distributions=pie_distributions)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/start_clarification')
@login_required
def start_clarification():
    token = session.get('access_token')
    user_info = get_user_profile(token)
    
    
    initial_message = start_clarification_conversation(user_info)
    
    
    session['conversation'] = [
        {"role": "assistant", "content": initial_message}
    ]
    session['conversation_finished'] = False
    
    return render_template('clarify.html', 
                          conversation=session['conversation'], 
                          conversation_finished=session['conversation_finished'])

@app.route('/clarify', methods=['POST'])
@login_required
def clarify():
    token = session.get('access_token')
    user_info = get_user_profile(token)
    user_input = request.form.get('user_input', '')
    
    
    conversation = session.get('conversation', [])
    
    
    conversation.append({"role": "user", "content": user_input})
    
    
    assistant_response = continue_clarification_conversation(conversation, user_input, user_info)
    
    
    conversation.append({"role": "assistant", "content": assistant_response})
    
    
    session['conversation'] = conversation
    
    
    if "Je pense que j'en sais assez pour te recommander des animés" in assistant_response:
        session['conversation_finished'] = True
    
    return render_template('clarify.html', 
                          conversation=session['conversation'], 
                          conversation_finished=session['conversation_finished'])

@app.route('/finish_clarification')
@login_required
def finish_clarification():
    
    session['conversation_finished'] = True
    
    return render_template('clarify.html', 
                          conversation=session.get('conversation', []), 
                          conversation_finished=True)

@app.route('/get_refined_recommendations')
@login_required
def get_refined_recommendations():
    token = session.get('access_token')
    user_info = get_user_profile(token)
    conversation = session.get('conversation', [])
    seen_titles = get_watched_titles(token, user_info["name"])
    
    
    print(f"Génération de recommandations affinées pour {user_info['name']}")
    print(f"Nombre de titres déjà vus: {len(seen_titles)}")
    print(f"Conversation: {len(conversation)} messages")
    
    
    llm_response = generate_refined_recommendations(conversation, user_info, seen_titles)
    
    
    import re
    recommendations = []
    if isinstance(llm_response, str) and "Raisonnement" in llm_response and "Titre" in llm_response:
        blocks = re.split(r'\n?-{3,}\n?', llm_response)
        for block in blocks:
            if "Titre" in block:
                champ = {}
                for line in block.splitlines():
                    if line.lower().startswith("raisonnement :"):
                        champ["raisonnement"] = line.split(":", 1)[1].strip()
                    elif line.lower().startswith("titre :"):
                        champ["titre"] = line.split(":", 1)[1].strip()
                    elif line.lower().startswith("description :"):
                        champ["description"] = line.split(":", 1)[1].strip()
                    elif line.lower().startswith("pourquoi :"):
                        champ["pourquoi"] = line.split(":", 1)[1].strip()
                if champ.get("titre"):
                    meta = get_anime_metadata(token, champ["titre"])
                    champ["episodes"] = meta.get("episodes", 12)
                    champ["duration"] = meta.get("duration", 24)
                    champ["cover"] = meta.get("cover")
                    champ["format"] = meta.get("format", "TV")
                    champ["id"] = meta.get("id")  
                    recommendations.append(champ)
    else:
        
        recommendations = [{
            "raisonnement": "Difficultés à trouver des recommandations adaptées",
            "titre": "Aucune recommandation trouvée",
            "description": llm_response if isinstance(llm_response, str) else "Erreur de génération des recommandations",
            "pourquoi": "Essayez de préciser différentes préférences ou explorer d'autres genres",
            "episodes": 0,
            "duration": 0
        }]
    
    session['recommendations'] = recommendations
    session['refined'] = True
    
    return redirect('/recommend')

if __name__ == '__main__':
    app.run(debug=True)
