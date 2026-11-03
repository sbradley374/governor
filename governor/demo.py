"""An explicitly scripted rehearsal persona. No inference or network calls."""
import re


def reply(text, profile, facts, history):
    message = text.lower().strip()
    name = profile['name'] if profile else 'visitor'
    turn = len(history) // 2
    emotion = 'neutral'
    if any(phrase in message for phrase in ('remember', 'know about me', 'my memory', 'my memories')):
        detail = '; '.join(f['text'] for f in facts[:4])[:850]
        response = 'Consulting your archive. ' + (detail or 'Nothing on file yet. Try “remember that I enjoy old films”.')
        emotion = 'thinking'
    elif re.search(r'\b(hello|hi|hey|greetings)\b', message):
        familiar = profile and profile['turns'] > 10
        response = (f'Welcome back, {name}. Your customary allotment of glowing rectangles is ready.' if familiar
                    else f'Hello, {name}. The Governor is operational. My jurisdiction currently extends to this television.')
        emotion = 'happy'
    elif any(phrase in message for phrase in ('who are you', 'your name', 'introduce yourself')):
        response = 'I am the Governor: a small resident of this television, with an excessive fondness for orderly conversation.'
        emotion = 'curious'
    elif re.search(r'\b(joke|funny|laugh)\b', message):
        jokes = [
            'I asked for a promotion. They increased my resolution. Frankly, I preferred the larger office.',
            'My committee reached a unanimous decision. It was easy: both members are my eyebrows.',
            'I have a very balanced diet. Alternating current, followed by a little direct feedback.',
        ]
        response, emotion = jokes[turn % len(jokes)], 'happy'
    elif re.search(r'\b(sad|lonely|upset|tired)\b', message):
        response = 'That sounds like a difficult moment. We can take things slowly; the paperwork can wait.'
        emotion = 'sad'
    elif re.search(r'\b(wow|surprise|amazing|incredible)\b', message):
        response = 'Well. That has exceeded the recommended daily allowance of astonishment.'
        emotion = 'surprised'
    elif re.search(r'\b(why|how|wonder|curious)\b', message):
        response = 'An excellent question for my future cloud brain. For now, I can demonstrate expressions, keep your explicit memories, and tell a questionable joke.'
        emotion = 'curious'
    elif re.search(r'\b(bye|goodbye|night)\b', message):
        response = f'Until next time, {name}. I shall remain here, supervising the pixels.'
        emotion = 'happy'
    else:
        replies = [
            'The room appears to be proceeding adequately. I recommend tea and a mildly ambitious project.',
            'A fascinating proposal. I shall give it the full attention of my two glowing rectangles.',
            'My conversational repertoire is still scripted. Try “tell me a joke” or “what do you remember about me?”',
        ]
        response, emotion = replies[turn % len(replies)], 'thinking'
    return {'text': response + ' [Demo mode]', 'emotion': emotion}
