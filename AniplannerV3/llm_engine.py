import openai
from rapidfuzz import fuzz

OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

def extract_titles(blocks, seen_titles, threshold):
    final_blocks = []
    titles_found = set()
    
    seen_titles_lower = set(t.lower() for t in seen_titles)
    
    
    print(f"Extraction à partir de {len(blocks)} blocks, {len(seen_titles)} titres déjà vus, threshold={threshold}")
    
    for block in blocks:
        lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
        reasoning = ""
        title = ""
        description = ""
        why = ""
        for l in lines:
            if l.lower().startswith("raisonnement :"):
                reasoning = l.split(":", 1)[1].strip()
            elif l.lower().startswith("titre :"):
                title = l.split(":", 1)[1].strip()
            elif l.lower().startswith("description :"):
                description = l.split(":", 1)[1].strip()
            elif l.lower().startswith("pourquoi :"):
                why = l.split(":", 1)[1].strip()
        if not title:
            continue
            
        title_lower = title.strip().lower()
        
        
        duplicate_found = False
        similar_title = None
        max_similarity = 0
        
        
        if title_lower in seen_titles_lower:
            print(f"❌ Titre exact déjà vu: '{title}'")
            continue
            
        
        for seen in seen_titles_lower:
            similarity = fuzz.ratio(title_lower, seen)
            if similarity > max_similarity:
                max_similarity = similarity
                similar_title = seen
                
            if similarity >= threshold:
                duplicate_found = True
                print(f"❌ Titre similaire trouvé: '{title}' est similaire à '{seen}' à {similarity}%")
                break
                
        if duplicate_found:
            continue
            
        
        if title_lower in titles_found:
            print(f"❌ Titre déjà recommandé dans cette session: '{title}'")
            continue
            
        print(f"✅ Titre accepté: '{title}' (similarité max: {max_similarity}% avec '{similar_title}')")
        titles_found.add(title_lower)
        final_blocks.append({
            "raisonnement": reasoning,
            "titre": title,  
            "description": description,
            "pourquoi": why
        })
        if len(final_blocks) == 3:
            break
    
    print(f"Extraction terminée: {len(final_blocks)} titres acceptés")
    return final_blocks

def generate_recommendations(user_profile, seen_titles):
    name = user_profile['name']
    genres = ", ".join(user_profile['genres'])
    favourites = ", ".join(user_profile['favourites'])
    threshold = 80  

    base_prompt = f"""
    Tu es un expert en animés avec une connaissance approfondie de MyAnimeList et AniList.

    Voici le profil de l'utilisateur {name} :
    - Genres préférés : {genres}
    - Animés favoris (à ne pas recommander, car déjà vus ou explicitement listés comme favoris) : {favourites}

    Recommande exactement 3 animés différents et non vus par {name}.
    Pour chaque recommandation :

    1.  **Raisonnement CoT (Chain-of-Thought) détaillé** :
        Explique clairement ta logique étape par étape.
        a.  Comment cette recommandation se connecte-t-elle spécifiquement aux genres préférés de {name} ({genres}) ? Sois précis.
        b.  En quoi cette recommandation est-elle distincte et complémentaire par rapport aux animés favoris de {name} ({favourites}) ? Souligne la nouveauté ou l'angle différent qu'elle apporte.
        c.  Quel est ton processus de pensée pour arriver à cette suggestion ? (Par exemple : "L'utilisateur aime X et Y, et son favori Z a telle caractéristique. Je cherche donc un animé qui combine X ou Y avec une caractéristique A ou B, tout en étant différent de Z sur l'aspect C.")

    2.  Présente ensuite la recommandation en respectant scrupuleusement le format suivant :

    ---
    Raisonnement : <Ton explication détaillée issue de l'étape 1. Ce texte doit refléter ton processus de pensée CoT et être spécifique au profil de {name}.>
    Titre : <Nom de l'animé>
    Description : <1 phrase concise et accrocheuse résumant l'animé.>
    Pourquoi : <1-2 phrases additionnelles qui renforcent la recommandation, en soulignant par exemple un aspect unique, une qualité reconnue (animation, musique, originalité du scénario) ou un attrait particulier pour {name} qui n'a pas été entièrement couvert dans le raisonnement principal.>
    ---

    **Exemple illustratif de la structure attendue pour UNE recommandation (le contenu doit être adapté au profil réel de {name}) :**
    ---
    Raisonnement : L'utilisateur {name} apprécie les genres 'Aventure' et 'Fantaisie'. Son animé favori 'Favori Alpha' est une épopée avec un vaste monde. Je propose 'Nouvelle Aventure Épique' car il partage le genre 'Aventure' et l'exploration d'un monde riche, mais se distingue par un système de magie original et une ambiance plus sombre, offrant une variation par rapport à 'Favori Alpha'. Mon processus a été de chercher un animé d'aventure fantastique bien noté, qui ne soit pas 'Favori Alpha', et qui introduise un élément distinctif.
    Titre : Nouvelle Aventure Épique
    Description : Un héros improbable se lance dans une quête périlleuse pour sauver son royaume d'une ancienne malédiction.
    Pourquoi : Cet animé est acclamé pour la complexité de ses personnages secondaires et la bande originale immersive qui amplifie chaque scène d'action.
    ---

    ⚠️ Le champ "Titre :" doit impérativement apparaître pour chaque animé. Ne saute jamais ce champ.
    Sois structuré, pertinent et engageant.
    Termine ta réponse globale par une phrase concise résumant ta stratégie de sélection pour l'ensemble des 3 recommandations.
    """

    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        attempts = 0
        all_blocks = []
        all_titles = set()
        prompt = base_prompt

        while attempts < 3 and len(all_blocks) < 3:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            full_text = response.choices[0].message.content.strip()
            blocks = [b for b in full_text.split("---") if "Titre" in b]
            new_blocks = extract_titles(blocks, seen_titles | all_titles, threshold)
            for block in new_blocks:
                
                all_titles.add(block["titre"])
            all_blocks.extend(new_blocks)
            attempts += 1
            
            if len(all_blocks) < 3:
                prompt = base_prompt + f"\nNe propose pas ces titres : {', '.join(list(seen_titles | all_titles))}"

        if len(all_blocks) < 3:
            return (
                f"⚠️ Seulement {len(all_blocks)} recommandation(s) valides après {attempts} tentatives :\n\n" +
                "\n\n---\n\n".join([
                    f"Raisonnement : {block['raisonnement']}\nTitre : {block['titre']}\nDescription : {block['description']}\nPourquoi : {block['pourquoi']}"
                    for block in all_blocks
                ]) +
                "\n\n🔁 Essaye d’élargir les critères ou de reformuler la demande."
            )

        return "\n\n---\n\n".join([
            f"Raisonnement : {block['raisonnement']}\nTitre : {block['titre']}\nDescription : {block['description']}\nPourquoi : {block['pourquoi']}"
            for block in all_blocks[:3]
        ])

    except Exception as e:
        return f"❌ Erreur OpenAI : {str(e)}"

def start_clarification_conversation(user_profile):
    """Démarre une conversation de clarification avec l'utilisateur"""
    
    name = user_profile['name']
    genres = ", ".join(user_profile['genres'])
    favourites = ", ".join(user_profile['favourites'])

    prompt = f"""
    Tu es un assistant spécialisé en recommandations d'animés qui pose des questions pour mieux comprendre les goûts de {name}.
    
    Tu as déjà ces informations :
    - Genres préférés : {genres}
    - Animés favoris : {favourites}
    
    IMPORTANT: 
    1. Sois très concis. Limite ta réponse à 3-4 phrases maximum. Ton message ne doit pas dépasser 3 lignes.
    2. Ne recommande JAMAIS d'animés spécifiques pendant cette conversation. Tu ne dois PAS mentionner de titres d'animés.
    3. Ton rôle est uniquement de poser des questions pour comprendre les préférences.
    
    Présente-toi en une phrase puis pose 1-2 questions ciblées pour mieux cerner ses préférences actuelles.
    Choisis parmi ces sujets:
    - Éléments spécifiques appréciés (ambiance, animation, personnages)
    - Recherche de similitudes ou nouveautés par rapport aux favoris
    - Durée préférée (séries courtes/longues)
    - Genres à éviter

    Ton message doit être court, direct et amical.
    """
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.7,
            max_tokens=150  
        )
        return response.choices[0].message.content
    except Exception as e:
        return "Salut ! Pour affiner mes recommandations, préfères-tu des séries longues ou courtes ? Y a-t-il des genres à éviter ?"

def continue_clarification_conversation(conversation, user_input, user_profile):
    """Continue la conversation avec l'utilisateur en fonction de sa réponse"""
    
    name = user_profile['name']
    genres = ", ".join(user_profile['genres'])
    favourites = ", ".join(user_profile['favourites'])
    
    system_prompt = f"""
    Tu es un assistant spécialisé en recommandations d'animés qui aide {name} à clarifier ses préférences.
    
    Tu connais déjà ces informations sur {name} :
    - Genres préférés : {genres}
    - Animés favoris : {favourites}
    
    IMPORTANT:
    1. Sois extrêmement concis. Limite tes réponses à 2-4 phrases maximum.
    2. Ne fais pas de longs paragraphes ou d'explications détaillées.
    3. Ne recommande AUCUN animé spécifique dans ta réponse. N'évoque pas de titres précis.
    4. Après 2 échanges, conclue la conversation avec une phrase de résumé très courte.
    5. À la fin de ton dernier message, inclus exactement cette phrase: "Je pense que j'en sais assez pour te recommander des animés"
    
    Ton objectif est de recueillir des informations essentielles de manière efficace, pas d'avoir une longue conversation ni de suggérer des titres.
    Si l'utilisateur te demande des recommandations, rappelle-lui poliment que tu collectes d'abord ses préférences et que tu lui proposeras des recommandations une fois la conversation terminée.
    """
    
    
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in conversation:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    
    messages.append({"role": "user", "content": user_input})
    
    
    conversation_length = sum(1 for msg in conversation if msg["role"] == "user")
    if conversation_length >= 2:
        messages.append({"role": "system", "content": "C'est le moment de conclure. Fais un résumé très court (1-2 phrases) de ce que tu as appris sur les préférences de l'utilisateur, sans recommander d'animés. Termine par la phrase de conclusion."})
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=200  
        )
        return response.choices[0].message.content
    except Exception as e:
        return "Merci pour ces précisions ! Je pense que j'en sais assez pour te recommander des animés maintenant."

def generate_refined_recommendations(conversation, user_profile, seen_titles):
    """Génère des recommandations affinées basées sur la conversation"""
    
    name = user_profile['name']
    genres = ", ".join(user_profile['genres'])
    favourites = ", ".join(user_profile['favourites'])
    threshold = 75  
    
    
    conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
    
    
    example_seen = list(seen_titles)[:5] if len(seen_titles) >= 5 else list(seen_titles)
    
    refined_prompt = f"""
    Tu es un expert en animés avec une connaissance approfondie de MyAnimeList et AniList.

    Voici le profil de l'utilisateur {name} :
    - Genres préférés : {genres}
    - Animés favoris (à ne pas recommander) : {favourites}
    
    IMPORTANT: L'utilisateur a déjà vu de nombreux animés dont voici quelques exemples : {', '.join(example_seen)}
    
    De plus, vous avez eu cette conversation pour clarifier les préférences :
    
    {conversation_text}

    Recommande exactement 3 animés différents et non vus par {name}.
    Pour chaque recommandation :

    1.  **Raisonnement CoT (Chain-of-Thought) détaillé** :
        Explique clairement ta logique étape par étape.
        a.  Comment cette recommandation se connecte-t-elle spécifiquement aux genres préférés de {name} ({genres}) ?
        b.  En quoi cette recommandation répond-elle aux préférences exprimées dans la conversation ?
        c.  Comment as-tu pris en compte les clarifications données par l'utilisateur pour arriver à cette suggestion ?

    2.  Présente ensuite la recommandation en respectant scrupuleusement le format suivant :

    ---
    Raisonnement : <Ton explication détaillée issue de l'étape 1. Ce texte doit refléter ton processus de pensée CoT et être spécifique aux préférences affinées de {name}.>
    Titre : <Nom de l'animé>
    Description : <1 phrase concise et accrocheuse résumant l'animé.>
    Pourquoi : <1-2 phrases additionnelles qui renforcent la recommandation, en soulignant un aspect particulièrement pertinent par rapport aux préférences affinées de l'utilisateur.>
    ---

    **Exemple illustratif de la structure attendue pour UNE recommandation (le contenu doit être adapté au profil et à la conversation) :**
    ---
    Raisonnement : L'utilisateur {name} a mentionné dans la conversation qu'il/elle préfère les séries courtes avec une ambiance sombre mais pas déprimante. Ses genres préférés incluent 'Thriller' et 'Mystère'. Je propose 'Titre d'Exemple' car c'est une série de 12 épisodes avec une esthétique sombre et une intrigue captivante. Ce n'est pas simplement un thriller standard, mais il intègre des éléments de mystère psychologique qui correspondent à ce que l'utilisateur recherche, tout en restant différent de ses favoris actuels.
    Titre : Titre d'Exemple
    Description : Un détective au passé trouble se retrouve plongé dans une affaire qui révèle des secrets bien plus profonds que prévus.
    Pourquoi : La série se démarque par sa narration non-linéaire et ses touches d'humour noir qui allègent l'atmosphère, exactement ce que l'utilisateur a décrit comme son équilibre idéal.
    ---

    ⚠️ Le champ "Titre :" doit impérativement apparaître pour chaque animé. Ne saute jamais ce champ.
    ⚠️ Ne recommande PAS d'animés que l'utilisateur a déjà vus ou mentionnés comme favoris.
    ⚠️ Assure-toi que tes recommandations sont distinctes et parfaitement adaptées aux préférences exprimées dans la conversation.
    
    Sois structuré, pertinent et engageant.
    Termine ta réponse globale par une phrase concise expliquant comment tes recommandations répondent spécifiquement aux préférences affinées de l'utilisateur.
    """
    
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        attempts = 0
        all_blocks = []
        all_titles = set()
        prompt = refined_prompt
        temperatures = [0.7, 0.8, 0.9]  

        while attempts < 5 and len(all_blocks) < 3:  
            
            current_temp = temperatures[min(attempts, len(temperatures)-1)]
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Tu es un expert en animés qui recommande des titres originaux et peu connus"},
                    {"role": "user", "content": prompt}
                ],
                temperature=current_temp,
                max_tokens=1200  
            )
            full_text = response.choices[0].message.content.strip()
            blocks = [b for b in full_text.split("---") if "Titre" in b]
            
            
            new_blocks = extract_titles(blocks, seen_titles | all_titles, threshold)
            
            for block in new_blocks:
                all_titles.add(block["titre"].lower())
            all_blocks.extend(new_blocks)
            attempts += 1
            
            
            if len(all_blocks) < 3:
                rejected_titles = list(all_titles)
                prompt = refined_prompt + f"""
                NOUVELLE TENTATIVE NÉCESSAIRE:
                - Tu as déjà suggéré ces titres qui ne conviennent pas: {', '.join(rejected_titles)}
                - Propose des titres COMPLÈTEMENT DIFFÉRENTS et moins connus
                - Concentre-toi sur des anime sortis entre 2010 et 2022 qui correspondent aux préférences
                - Cherche des pépites méconnues du grand public mais appréciées par les critiques
                - Évite ABSOLUMENT les grands classiques et les anime ultra-populaires
                """

        
        if len(all_blocks) < 3 and attempts >= 5:
            
            threshold = 65  
            prompt = refined_prompt + """
            ASSOUPLISSEMENT DES CRITÈRES:
            - Nous avons besoin de recommandations vraiment originales
            - N'hésite pas à suggérer des anime moins connus ou des œuvres de niche
            - L'important est de respecter les thèmes et préférences mentionnés dans la conversation
            - Utilise des anime de TOUTES les périodes (années 90, 2000, 2010, 2020)
            - Respecte SCRUPULEUSEMENT le format demandé avec le champ "Titre :" bien identifiable
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "Tu es un expert en recommandations d'anime originaux et peu connus."},
                           {"role": "user", "content": prompt}],
                temperature=1.0,  
                max_tokens=1200
            )
            full_text = response.choices[0].message.content.strip()
            blocks = [b for b in full_text.split("---") if "Titre" in b]
            new_blocks = extract_titles(blocks, seen_titles | all_titles, threshold)
            all_blocks.extend(new_blocks)

        
        if len(all_blocks) == 0:
            return """
            ⚠️ Je n'ai pas pu générer de recommandations qui correspondent à la fois à vos préférences ET qui ne sont pas similaires à ce que vous avez déjà vu.
            
            Suggestions :
            1. Essayez de préciser des genres ou thèmes différents de ce que vous avez l'habitude de regarder
            2. Demandez explicitement des recommandations pour découvrir de nouveaux genres
            3. Mentionnez si vous êtes ouvert à des anime plus anciens ou plus récents
            
            Vous pouvez relancer une conversation pour affiner vos préférences différemment.
            """

        return "\n\n---\n\n".join([
            f"Raisonnement : {block['raisonnement']}\nTitre : {block['titre']}\nDescription : {block['description']}\nPourquoi : {block['pourquoi']}"
            for block in all_blocks[:3]
        ])
    except Exception as e:
        return f"❌ Erreur lors de la génération des recommandations : {str(e)}"
