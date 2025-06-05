import os
import datetime
import json
from flask import session, redirect, request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',  
    'https://www.googleapis.com/auth/calendar.readonly' 
]
CLIENT_SECRETS_FILE = 'credentials.json'

def start_google_auth():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:5000/gcal_callback'
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

def handle_google_callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri='http://localhost:5000/gcal_callback'
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session['google_credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    session['google_connected'] = True
    return redirect('/calendar')

def insert_calendar_event(anime_title, num_episodes=1, start_time=None):
    if 'google_credentials' not in session:
        return False

    creds_data = session['google_credentials']
    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    service = build('calendar', 'v3', credentials=creds)

    episode_duration = 24
    total_duration = num_episodes * episode_duration

    
    start = datetime.datetime.fromisoformat(start_time)
    end = start + datetime.timedelta(minutes=total_duration)

    
    timezone = "Africa/Casablanca"

    event = {
        'summary': f'Marathon animé : {anime_title} – {num_episodes} épisode(s)',
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': timezone
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': timezone
        },
        'reminders': {
            'useDefault': False,
            'overrides': [{'method': 'popup', 'minutes': 10}]
        }
    }

    try:
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        return True if 'id' in event_result else False
    except Exception as e:
        print(f"Erreur lors de l'insertion de l'événement : {e}")
        
        if hasattr(creds, 'refresh') and hasattr(creds, 'token_uri') and creds.refresh_token:
            try:
                creds.refresh(Request()) 
                session['google_credentials']['token'] = creds.token 
                
                event_result = service.events().insert(calendarId='primary', body=event).execute()
                return True if 'id' in event_result else False
            except Exception as refresh_error:
                print(f"Erreur lors du rafraîchissement du token : {refresh_error}")
                return False
        return False

def get_upcoming_events(max_results=10, days_ahead=30):
    """Récupère les événements à venir du calendrier Google de l'utilisateur."""
    if 'google_credentials' not in session:
        return []

    creds_data = session['google_credentials']
    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data.get('refresh_token'),
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    try:
        service = build('calendar', 'v3', credentials=creds)
        now = datetime.datetime.utcnow()
        time_min = now.isoformat() + 'Z'  
        time_max = (now + datetime.timedelta(days=days_ahead)).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary', timeMin=time_min, timeMax=time_max,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        formatted_events = []
        for event in events:
            start_raw = event['start'].get('dateTime', event['start'].get('date'))
            end_raw = event['end'].get('dateTime', event['end'].get('date'))
            
            all_day = 'T' not in start_raw 

            if all_day:
                start_dt = datetime.datetime.strptime(start_raw, '%Y-%m-%d').date()
                
                end_dt = datetime.datetime.strptime(end_raw, '%Y-%m-%d').date()
                
                if (end_dt - start_dt).days == 1:
                     display_end_dt = start_dt 
                else:
                     display_end_dt = end_dt - datetime.timedelta(days=1) 

            else:
                
                start_dt = datetime.datetime.fromisoformat(start_raw.replace('Z', '+00:00'))
                end_dt = datetime.datetime.fromisoformat(end_raw.replace('Z', '+00:00'))
                display_end_dt = end_dt


            formatted_events.append({
                'summary': event.get('summary', 'Sans titre'),
                'start': start_dt,
                'end': display_end_dt, 
                'all_day': all_day,
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'id': event['id'],
                'is_anime_event': 'Marathon animé' in event.get('summary', '') or 'animé' in event.get('summary', '').lower()
            })
        return formatted_events

    except Exception as e:
        print(f"Erreur lors de la récupération des événements: {e}")
        
        return []

def get_calendar_stats():
    """Calcule des statistiques simples sur les événements d'animés planifiés."""
    events = get_upcoming_events(max_results=250, days_ahead=365) 
    anime_events = [e for e in events if e['is_anime_event']]
    
    total_anime_events = len(anime_events)
    total_hours_planned = 0
    upcoming_this_week = 0
    now_date = datetime.datetime.now().date() 
    
    for event in anime_events:
        if not event['all_day']:
            duration = event['end'] - event['start'] 
            total_hours_planned += duration.total_seconds() / 3600
        
        
        event_start_date = event['start'] if event['all_day'] else event['start'].date()
        if now_date <= event_start_date < (now_date + datetime.timedelta(days=7)):
            upcoming_this_week += 1
            
    return {
        'total_anime_events': total_anime_events,
        'total_hours_planned': round(total_hours_planned, 1),
        'upcoming_this_week': upcoming_this_week
    }
