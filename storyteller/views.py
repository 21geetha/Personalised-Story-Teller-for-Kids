from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
import requests
import io
import base64
import os
import uuid
from gtts import gTTS
from google.cloud import texttospeech as tts
from deep_translator import GoogleTranslator

#  Gemini API 
API_KEY = 'AIzaSyCtWmjRk5yl36iN3w2TX5opCrwomgAat60'
GEMINI_API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}'

# DreamStudio API Key
STABILITY_API_KEY = 'sk-pR42wkfKeX0BkGt7GGzByWuJoQkmTFWcWOE7JigZqWf2fagk'

#  Send Prompt to Gemini 
def send_to_gemini(prompt):
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(GEMINI_API_URL, json=data)
    if response.status_code == 200:
        try:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            return "Sorry, something went wrong with story generation."
    else:
        return f"Error: {response.status_code} - {response.text}"

# Generate Image from Visual Prompt using DreamStudio
def generate_image_from_story(visual_prompt):
    url = "https://api.stability.ai/v1/generation/stable-diffusion-v1-6/text-to-image"
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "text_prompts": [{"text": visual_prompt}],
        "cfg_scale": 7,
        "clip_guidance_preset": "FAST_BLUE",
        "height": 512,
        "width": 512,
        "samples": 1,
        "steps": 30
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        result = response.json()
        image_base64 = result["artifacts"][0]["base64"]
        os.makedirs("static/generated", exist_ok=True)
        filename = f"story_image_{uuid.uuid4().hex[:8]}.png"
        relative_path = f"generated/{filename}"
        full_path = os.path.join("static", relative_path)
        with open(full_path, "wb") as f:
            f.write(base64.b64decode(image_base64))
        return relative_path
    else:
        print("Image generation failed:", response.text)
        return None

# Extract Visual Prompt from Story using Gemini
def extract_visual_prompt(story_text):
    visual_prompt_instruction = (
        "From the following story, extract a short and vivid visual scene description suitable for image generation. "
        "Keep it under 20 words. Focus on a key visual moment or setting:\n\n"
        f"{story_text}"
    )
    return send_to_gemini(visual_prompt_instruction)

# Translate function using deep-translator 
def translate_story(text, target_lang):
    lang_map = {
        'hi': 'hi',  
        'te': 'te'    
    }
    if target_lang not in lang_map:
        return text
    try:
        return GoogleTranslator(source='auto', target=lang_map[target_lang]).translate(text)
    except Exception as e:
        print("Translation error:", e)
        return text

# Text-to-Speech (gTTS for local narration)
def generate_audio(text, lang_code):
    tts = gTTS(text=text, lang=lang_code)
    audio_path = os.path.join('static', 'output.mp3')
    tts.save(audio_path)
    return audio_path

#  View to handle translated narration
def view_translated_story(request):
    if request.method == 'POST':
        original_story = request.POST.get('story')
        language = request.POST.get('language')  
        translated_story = translate_story(original_story, language)
        audio_path = generate_audio(translated_story, language)
        return render(request, 'translate.html', {
            'story': translated_story,
            'audio_file': '/' + audio_path,
            'lang': language
        })
    return render(request, 'translate.html')

# Main Story Form View
def story_form(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        age = request.POST.get('age')
        gender = request.POST.get('gender')
        interest = request.POST.get('interest')
        story_type = request.POST.get('story_type')
        moral = request.POST.get('moral', '')
        emotion = request.POST.get('emotion', '')
        voice = request.POST.get('voice') or "en-US-Standard-C"
        lang = request.POST.get('lang', 'en-US')

        if story_type == 'bedtime':
            prompt = f"""
            You are a story writer for small kids.

            Write a short bedtime story for a {gender} child named {name}, who is {age} years old.
            Start with a classic line like "Once upon a time" or "One day".
            
            RULES:
            - Use VERY SIMPLE words only (example: happy, sad, cat, sun, toy, hug, run, play).
            - DO NOT use difficult or emotional words (like magical, cheerful, wilted, giggling, snuggled, embraced).
            - Keep every sentence short and easy to say out loud.
            - Use the child’s interest: "{interest}" as the main theme.
            - {name} should be the main character.
            - The story should end with a very simple, happy moral: "{moral}".
            - Keep it under 300 words.
            """


        elif story_type == 'educational':
            prompt = f"""
                Create a simple and fun story that explains "{interest}" to a {gender} child named {name}, who is {age} years old.
                Begin with a gentle storytelling line like "One day", "In a small town", or "Once upon a time".
                Use only very very very very very simple and easy English words and short sentences.
                Avoid any difficult words or complex ideas.
                Make {name} the main character who explores or discovers the topic.
                Keep the explanation natural through storytelling, not like a textbook.
                End with a small takeaway or something nice the child learns.
                Keep the story under 300 words.
            """

        elif story_type == 'emotion':
            prompt = f"""
            You are a kind storyteller helping a child feel better.

            Write a comforting story for a {gender} child named {name}, age {age}, who is feeling "{emotion}".
            
             RULES:
            - Start with a soft line like "Once upon a time", "There was a little boy/girl", or "One day".
            - Use ONLY small, safe words. Example: happy, sad, hug, toy, sun, cloud, play, love.
            - DO NOT use words like anxious, depressed, lonely, or magical.
            - Keep each sentence short.
            - The story should make the child feel safe, strong, and happy.
            - Remind the child they are not alone and they are loved.
            - End with a gentle positive message.
            - Keep it under 300 words.
            """

        else:
            prompt = "Invalid story type selected."


        story = send_to_gemini(prompt)

        if story_type == 'educational':
            visual_prompt = (
                f"A clean, high-quality educational illustration of the '{interest}' concept, with simple shapes and no text, in a style suitable for children aged {age}"
            )
        elif story_type == 'emotion':
                visual_prompt = (
                    f"A soft, comforting illustration for a {age}-year-old child feeling {emotion}, in a calm and child-friendly style"
                )
        else: 
                visual_prompt = extract_visual_prompt(story)


        image_path = generate_image_from_story(visual_prompt)

        return render(request, 'story.html', {
            'story': story,
            'name': name,
            'voice': voice,
            'lang': lang,
            'image_path': image_path,
            'gender': gender,
            'emotion': emotion if story_type == 'emotion' else ''
        })

    return render(request, 'form.html')

# Google Cloud Text-to-Speech (optional, for high-quality English narration) 
def text_to_speech(request):
    if request.method == 'POST':
        text = request.POST.get('story')
        voice_name = request.POST.get('voice') or "en-US-Standard-C"
        language_code = "-".join(voice_name.split("-")[:2])
        client = tts.TextToSpeechClient()
        synthesis_input = tts.SynthesisInput(text=text)
        voice_params = tts.VoiceSelectionParams(language_code=language_code, name=voice_name)
        audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3)
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )
        return HttpResponse(response.audio_content, content_type='audio/mpeg')

# Authentication 
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password")
    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
        else:
            User.objects.create_user(username=username, password=password)
            messages.success(request, "Registration successful. Please log in.")
            return redirect('login')
    return render(request, 'register.html')

def home_view(request):
    return render(request, 'home.html')

def logout_view(request):
    logout(request)
    return redirect('login')


## stories data
stories_data = [
  {
    "id": 1,
    "title": "🐶 Ramu and the Lost Puppy",
    "category": "Honesty",
    "content": """Ramu was a kind little boy. He lived in a small village. One day, while walking home from school, Ramu saw a small puppy near a tree. The puppy looked scared and hungry.
Ramu looked around. No one was there.
“This puppy is so cute,” Ramu said. “I want to take it home.”
But Ramu also thought, “Maybe someone is looking for this puppy.”
He picked up the puppy and took it to the village square. He asked people, “Did anyone lose a puppy?”
An old man said, “I think it belongs to Mr. Sharma. His puppy ran away this morning.”
Ramu went to Mr. Sharma’s house. Mr. Sharma saw the puppy and smiled.
“Oh! You found my Tommy! Thank you so much!” he said.
Ramu gave the puppy to Mr. Sharma.
Mr. Sharma said, “You are a very honest boy. You could have kept the puppy, but you didn’t. I am proud of you.”
Ramu smiled and said, “I just did what is right.”
Mr. Sharma gave Ramu a mango from his garden and said, “Honesty is a gift. Always keep it.”
Ramu went home feeling happy. He did not keep the puppy, but he did the right thing.
""",
    "moral": "Honesty is the best policy."
  },
  {
    "id": 2,
    "title": "🧒🏽 Meena and the Magic Pencil",
    "category": "Honesty",
    "content": """Meena was a smart and kind girl. She loved to draw. One day, while walking to school, she found a shiny pencil on the road. It looked new and beautiful.
She picked it up and saw some letters on it. It said, “This pencil belongs to Anu.”
Meena knew Anu. She was her classmate.
“I should give this back to Anu,” Meena thought.
But then, she looked at the pencil again. It was so pretty. It had stars and colors on it.
“I want to keep it,” Meena said to herself. “Anu may not miss it.”
But her heart said, “It is not yours. You must return it.”
At school, Meena saw Anu. Anu looked sad.
“What happened?” Meena asked.
“I lost my favorite pencil,” Anu said. “My uncle gave it to me.”
Meena felt bad. She took the pencil from her bag and gave it to Anu.
“Here it is! I found it near the road,” Meena said.
Anu smiled and hugged Meena.
“Thank you! You are honest and kind,” Anu said.
The teacher saw this and said, “Meena, you did a good thing. You are honest. I am proud of you.”
Meena felt happy. She knew she did the right thing.
""",
    "moral": "Always be honest, even when it is hard."
  },
  {
    "id": 3,
    "title": "🐦 Tina and the Little Bird",
    "category": "Kindness",
    "content": """Tina was a small girl. She lived in a pretty house with her parents. She loved flowers, trees, and animals.
One morning, Tina went to the garden. She heard a soft sound. “Tweet… tweet…”
She looked under a bush and saw a little bird. The bird was hurt. Its wing was bleeding.
“Oh no! Poor bird,” said Tina. She ran inside and got a small box.
She gently picked up the bird and put it in the box.
“Don’t be scared. I will help you,” she said.
Tina told her mother. Her mother gave some water and soft cotton.
Tina cleaned the bird’s wing slowly. Then she gave the bird some rice and water.
The bird stayed with Tina for two days.
On the third day, the bird flapped its wings.
“It is better now!” Tina said with a smile.
She took the box outside and opened it.
The bird looked at Tina and flew away.
“Bye-bye, little bird,” said Tina, waving her hand.
Next day, the bird came back! It sat on the tree and sang a happy song.
“Tweet tweet!” it sang.
Tina laughed. “I’m happy you’re fine,” she said.
Every day, the bird came and sang for Tina.
""",
    "moral": "Kindness is always good."
  },
  {
    "id": 4,
    "title": "🧒🏻 Aarav and the Thirsty Dog",
    "category": "Kindness",
    "content": """It was a hot summer day. The sun was shining bright. Aarav, a little boy, was playing in front of his house.
Suddenly, he saw a dog walking slowly. The dog looked tired. Its tongue was out, and it was panting.
“Oh no, the dog looks thirsty,” Aarav said.
He ran inside and told his mother, “Mom, a dog outside is very thirsty. Can I give it some water?”
His mother smiled and said, “Yes, take this bowl and give clean water.”
Aarav took the bowl and placed it near the dog. The dog looked at him and slowly came closer. It drank the water very fast.
Aarav sat nearby and watched. “Poor dog. You must be very hot,” he said softly.
After drinking, the dog wagged its tail. It looked happy.
Aarav smiled. “I’m happy you feel better now.”
Every day after that, Aarav kept a bowl of water outside his house. Birds, cats, and dogs came to drink.
His friends asked, “Why do you do this every day?”
Aarav said, “Because animals also need water. We must be kind to them.”
His friends also started keeping water outside their homes.
One day, Aarav’s teacher heard about it and told the class, “Aarav showed kindness. We all should care for animals.”
Aarav felt proud but said, “I just wanted to help.”
""",
    "moral": "Kindness makes the world better."
  },
  {
    "id": 5,
    "title": "🐜 The Ant and the Rainy Day",
    "category": "Hard Work",
    "content": """Once there was a small ant. Every day, the ant worked hard. It carried food to its home. It worked in the hot sun and never stopped.
Other animals laughed at the ant.
“Why are you working so hard?” they asked. “Enjoy the sun!”
The ant said, “Rainy days will come. I need food to stay safe.”
But no one listened. They played all day.
Soon, the rainy season came. It rained and rained. The ground was wet and muddy. The animals had no food. They were cold and hungry.
The ant was inside its warm home. It had lots of food. It was safe.
One day, a cold squirrel came to the ant’s house.
“Please help me,” said the squirrel. “I have no food.”
The kind ant shared its food and said, “Next time, work hard like me.”
The squirrel nodded. “I will. Thank you.”
""",
    "moral": "Hard work helps you in tough times."
  },
  {
    "id": 6,
    "title": "🌱 Rina and the Plant",
    "category": "Hard Work",
    "content": """Rina was a little girl. She wanted to grow a flower plant. Her grandma gave her some seeds.
Rina planted the seeds in a pot. Every day, she gave water and kept it in the sun.
Her friends said, “It’s boring. The plant is so small.”
But Rina didn’t stop. She watered the plant every day.
One week passed. Two weeks passed. Still, the plant was small.
Rina smiled and said, “I will not give up.”
After one month, a small flower bloomed. Then more flowers came. The plant was big and beautiful!
Her friends said, “Wow! Your flowers are so pretty!”
Rina said, “Because I worked hard and waited.”
""",
    "moral": "Hard work and patience bring success."
  },
  {
    "id": 7,
    "title": "🎒 Ravi and His School Bag",
    "category": "Responsibility",
    "content": """Ravi was a young boy who went to school every day. His mother always packed his school bag for him.
One day, Ravi said, “I am a big boy now. I want to pack my own bag!”
His mother smiled and said, “Okay, Ravi. From now on, you are responsible for your bag.”
The next day, Ravi packed his bag. But he forgot to put in his homework book.
At school, the teacher asked, “Ravi, where is your homework?”
Ravi looked in his bag. “Oh no!” he said. “I forgot it at home.”
The teacher said, “Ravi, you must be responsible. It is your duty to bring everything you need.”
Ravi felt sad. “I will not forget again,” he promised.
That evening, Ravi made a list of things to pack: books, lunch box, pencil box, and homework.
Every night, he checked his list before sleeping. He packed everything carefully.
One week later, his teacher said, “Well done, Ravi! You have everything. You are becoming responsible.”
Ravi felt proud. He smiled and said, “I do it myself now. My mother is happy too!”
""",
    "moral": "Being responsible means doing your duties on your own."
  },
  {
    "id": 8,
    "title": "🐶 Maya and Bruno the Dog",
    "category": "Responsibility",
    "content": """Maya was a little girl who loved animals. One day, her father brought home a puppy.
“Wow! A puppy!” Maya shouted with joy.
“This is Bruno,” her father said. “But remember, Maya, having a pet is a big responsibility.”
Maya nodded. “I will take care of him!”
At first, Maya played with Bruno every day. She gave him food and water. She took him for walks.
But after a few days, Maya forgot. She watched TV and played games. She didn’t give Bruno food on time.
Bruno looked sad and weak.
One morning, her father said, “Maya, Bruno looks sick. You are not taking care of him.”
Maya felt sorry. She hugged Bruno and said, “I’m so sorry, Bruno. I forgot my promise.”
From that day, Maya made a plan. She woke up early to feed Bruno. She played with him and kept his bed clean.
Bruno became happy again. He wagged his tail and licked Maya’s face.
Her father smiled and said, “Good job, Maya! You are now a responsible pet owner.”
Maya said, “I love Bruno. I will always take care of him.”
""",
    "moral": "Responsibility means taking care of what you promise."
  },
  {
    "id": 9,
    "title": "🌟 Sita Shares Her Lunch",
    "category": "Selflessness",
    "content": """Sita was a kind girl. She went to school every day with a big smile.
One day, during lunch break, she sat under a tree to eat. She opened her lunch box and saw tasty food – rice, vegetables, and sweets.
Just then, she saw her friend Anu sitting alone. Anu looked sad.
Sita asked, “What happened, Anu?”
Anu said softly, “I forgot my lunch today. I am very hungry.”
Sita smiled and said, “Don’t worry. Let’s share my lunch!”
She gave half of her food to Anu. They both ate happily.
Anu said, “Thank you, Sita. You are very kind.”
Sita replied, “It feels good to share. I’m happy you are not hungry.”
The teacher saw them and said, “Sita, you are selfless. You care for others more than yourself. That is a very good thing.”
""",
    "moral": "Selflessness is sharing and caring without expecting anything in return."
  },
  {
    "id": 10,
    "title": "🐥 The Hen and the Cold Night",
    "category": "Selflessness",
    "content": """One winter night, it was very cold. A little hen was sitting in her nest with her chicks.
Suddenly, she saw a tiny bird sitting alone on a tree. The bird was shivering.
The hen called out, “Come inside my nest. It’s warm here.”
The bird said, “But there is no space.”
The hen said, “I will make space. You are not alone.”
She opened her wings and let the bird sit close. Now all the chicks and the bird were warm.
The hen could not sleep well, but she was happy.
In the morning, the bird said, “Thank you. You saved me.”
The hen smiled, “Helping others is more important than my sleep.”
""",
    "moral": "Being selfless means putting others before yourself."
  },
  {
    "id": 11,
    "title": "The Bundle of Sticks",
    "category": "Unity",
    "content": """Once upon a time, there was a farmer. He had four sons. The sons always fought with each other. They never worked together.
One day, the farmer got an idea. He took four sticks and tied them together.
He gave the bundle to his first son and said, “Break this.”
The son tried hard but could not break the bundle.
Then the second son tried. He also failed.
The third and fourth sons also tried, but the sticks stayed strong.
Then the farmer untied the bundle and gave one stick to each son.
“Now break your stick,” he said.
Snap! All the sons broke the sticks easily.
The farmer said, “When you fight, you are weak. But when you stay together, you are strong. Just like the sticks.”
The sons understood the lesson and said, “We will stay united from now.”
""",
    "moral": "Unity is strength."
  },
  {
    "id": 12,
    "title": "🐦 The Birds in the Net",
    "category": "Unity",
    "content": """A group of birds lived in a forest. Every morning, they flew together to find food.
One day, they saw many grains on the ground.
“Yummy!” said one bird. “Let’s eat!”
But the oldest bird said, “Wait! This looks like a trap.”
The others didn’t listen. They flew down to eat.
Suddenly — SNAP! — a net closed over them.
The birds were scared. “What do we do now?” they cried.
The old bird said, “We must work together. Let’s all fly up at the same time, carrying the net.”
All the birds flapped their wings together.
Up, up they flew, carrying the net with them!
They flew to a mouse friend, who cut the net and set them free.
They cheered, “We are safe because we stayed united!”
""",
    "moral": "When we work together, we can solve big problems."
  },
  {
    "id": 13,
    "title": "🎻 Rani Learns to Play the Violin",
    "category": "Practice makes perfect",
    "content": """Rani was a little girl who loved music. One day, her father gave her a small violin.
“I want to play a song,” Rani said.
She tried to play, but the sound was bad. "Screech! Scratch!" It did not sound like music.
Rani felt sad. “I can’t do it,” she said.
Her mother smiled and said, “Don’t worry. Just keep practicing every day.”
So Rani practiced for 10 minutes every morning. Some days were hard, but she didn’t stop.
One week passed… the sound got a little better.
Two weeks passed… she could play a small tune.
One month later, Rani played a full song at school. Everyone clapped!
Her teacher said, “Well done, Rani. You are good because you practiced.”
Rani smiled. “Now I know — practice makes perfect!”
""",
    "moral": "Practice makes you better, little by little."
  },
  {
    "id": 14,
    "title": "🏏 Arjun and the Cricket Game",
    "category": "Practice makes perfect",
    "content": """Arjun loved playing cricket, but he was not good at batting.
Every time he played, he got out quickly.
One day, he said to his brother, “I want to be a good batsman.”
His brother said, “You can. You just need to practice every day.”
So Arjun went to the field every morning. He practiced hitting the ball again and again.
Some days it was hot. Some days he was tired. But he didn’t stop.
After two months, there was a school match.
Arjun went to bat. This time, he hit the ball hard — four runs! six runs!
He made the highest score in the match!
His coach said, “You did it, Arjun!”
Arjun smiled and said, “I practiced a lot. That’s why I won.”
""",
    "moral": "Keep practicing — you will get better!"
  },
  {
    "id": 15,
    "title": "The Little Frog That Didn’t Give Up",
    "category": "Never give up",
    "content": """One day, a group of frogs were jumping through a forest.
Two little frogs fell into a deep pit.
The other frogs looked down and said, “It’s too deep! You will never get out!”
The two frogs tried to jump up. They jumped again and again.
But the frogs above kept shouting, “It’s no use! You can’t do it!”
One frog got tired. He listened to them and gave up.
But the other frog did not stop. He kept jumping.
Again and again, he tried. His legs hurt, but he still jumped.
Finally — BOING! — he jumped out!
The frogs were surprised and said, “How did you do it?”
Then they found out — the frog was deaf! He couldn’t hear them say “You can’t.”
He thought they were cheering him. So he kept trying and never gave up.
""",
    "moral": "Never give up, even when others say you can’t."
  },
  {
    "id": 16,
    "title": "✏ Tina Learns to Write",
    "category": "Never give up",
    "content": """Tina was a small girl. She wanted to write her name.
Her teacher wrote “TINA” on the board.
Tina tried, but her letters were messy.
She said, “I can’t do it. It’s too hard!”
Her teacher smiled and said, “You can. Just keep trying.”
Every day, Tina practiced writing her name.
Some days her letters looked better. Some days they looked worse.
But Tina didn’t stop.
After two weeks, she wrote “TINA” perfectly!
Her teacher clapped. “You did it!”
Tina smiled and said, “I didn’t give up!”
""",
    "moral": "If you keep trying, you will succeed. Never give up!"
  },
  {
    "id": 17,
    "title": "The Boy Who Cried Wolf",
    "category": "Always tell the truth",
    "content": """Once there was a boy named Ramu. He looked after sheep on a hill.
One day, Ramu felt bored. He shouted, “Wolf! Wolf! A wolf is coming!”
The villagers ran up the hill to help.
But there was no wolf. Ramu laughed. “Ha ha! I was joking!”
The villagers were angry and went back.
The next day, Ramu shouted again, “Wolf! Wolf!”
The villagers came running again. Still, there was no wolf. Ramu laughed again.
The villagers said, “Don’t do this again!”
On the third day, a real wolf came. The wolf ran to the sheep.
Ramu shouted, “Wolf! Wolf! Please help!”
But this time, no one came.
The wolf ran away with a sheep. Ramu cried.
He said, “I should have told the truth.”
""",
    "moral": "Always tell the truth. If you lie, people will not believe you when you really need help."
  },
  {
    "id": 18,
    "title": "Meena and the Broken Vase",
    "category": "Always tell the truth",
    "content": """Meena was playing ball inside the house. Her mother had told her, “Don’t play here.”
But Meena forgot. She threw the ball, and it hit a flower vase. The vase broke.
“Oh no!” Meena said. She was scared.
Her mother came in and asked, “What happened?”
Meena wanted to lie, but she took a deep breath and said, “I broke the vase. I’m sorry.”
Her mother looked at her.
“Thank you for telling the truth,” she said. “I’m happy you were honest.”
Meena said, “I won’t play ball inside again.”
Her mother hugged her and said, “It’s okay. We can fix the vase. But always tell the truth.”
""",
    "moral": "Telling the truth is always the right thing, even when it’s hard."
  },
  {
    "id": 19,
    "title": "The Elephant and the Mouse",
    "category": "Respect everyone big or small",
    "content": """One day, a big elephant was walking through the forest. He saw a small mouse running.
The elephant laughed and said, “You are so tiny! You can’t do anything!”
The mouse felt sad but said nothing.
Later that day, the elephant got caught in a big net set by hunters. He could not move.
He cried, “Help! Somebody help me!”
The mouse heard his voice and ran to help.
“Don’t worry,” said the mouse. He used his sharp teeth to cut the ropes of the net.
Soon, the elephant was free!
“Thank you, little friend!” said the elephant. “I was wrong to laugh at you.”
The mouse smiled and said, “Everyone is important, big or small.”
""",
    "moral": "Respect everyone, even if they are small. Everyone can help."
  },
  {
    "id": 20,
    "title": "🧹 Rani and the School Cleaner",
    "category": "Respect everyone big or small",
    "content": """Rani was a smart and kind girl. She said "good morning" to her teachers every day.
But she never smiled at the cleaner in her school. She thought, “He is not a teacher, so he is not important.”
One day, Rani slipped and fell in the hallway. Her books fell too.
The cleaner saw her and quickly helped her up.
“Are you okay?” he asked kindly. He picked up her books and gave her water.
Rani felt shy. “Thank you so much,” she said.
That day, Rani learned something important.
From the next day, she smiled at the cleaner and said, “Good morning, uncle!”
The cleaner smiled back.
""",
    "moral": "Respect all people — not by their job or size, but by their kindness."
  },
  {
    "id": 21,
    "title": "The Clever Crow",
    "category": "Every problem has a solution",
    "content": """It was a hot day. A crow was very thirsty. He flew here and there looking for water.
At last, he saw a pot under a tree. He flew down quickly and looked inside.
“There is some water!” he said. But the water was very low. He could not reach it.
The crow looked around and thought hard.
Then he got an idea!
He picked up small stones nearby and dropped them into the pot one by one.
Slowly, the water came up. The crow drank the water and flew away happily.
""",
    "moral": "Every problem has a solution if you think carefully."
  },
  {
    "id": 22,
    "title": "🎈 Neha and the Balloon",
    "category": "Every problem has a solution",
    "content": """Neha was a little girl who loved balloons. One day, she got a big red balloon at the market.
She held it happily as she walked home.
But suddenly — POP! — the balloon hit a thorn and burst.
Neha felt very sad. She sat down and cried.
Her friend Raju saw her and asked, “Why are you crying?”
“My balloon is gone,” Neha said.
Raju thought and said, “Let’s make a paper balloon!”
They went home and got some paper. With help from Neha’s mother, they made a paper balloon and painted it with red color.
Neha smiled. “It’s even better than the old one!”
She hung it in her room and looked at it every day.
""",
    "moral": "When something goes wrong, don’t be sad. Try to find a new way. Every problem has a solution."
  },
  {
    "id": 23,
    "title": "The Bees and the Big Flower",
    "category": "Teamwork makes the dream work",
    "content": """One sunny morning, many bees flew out of their hive to collect nectar.
They saw a big flower in the garden.
“We can make lots of honey with this flower!” said one bee.
But the flower was very large, and one bee could not do it alone.
“I need help,” said the little bee.
Soon, more bees came. Some collected nectar. Some cleaned the hive. Others made space for honey.
All the bees worked together.
By evening, the hive was full of sweet honey.
The queen bee said, “Well done! You all worked as a team.”
The bees smiled. “Yes! Teamwork makes the dream work!”
""",
    "moral": "Working together helps us do big things easily."
  },
  {
    "id": 24,
    "title": "🏏 The Cricket Match",
    "category": "Teamwork makes the dream work",
    "content": """There was a cricket match at school. Team A had good players but they all wanted to play alone.
Team B had average players, but they helped each other and played as a team.
In the match, Team A hit big shots, but they got out quickly. No one listened to each other.
Team B took turns, gave tips, and cheered for one another.
At the end, Team B won the game!
Everyone clapped!
A player from Team A said, “How did you win?”
Team B’s captain said, “We worked together. That’s the secret.”
The teacher said, “Great job! Teamwork is the best way to win.”
""",
    "moral": "When we work as a team, we can do anything better and faster."
  }
]

def choose_story(request):
    return render(request, 'choose.html', {"stories": stories_data})

def view_story(request, story_id):
    story = next((s for s in stories_data if s["id"] == story_id), None)
    if story:
        return render(request, 'view_story.html', {"story": story})
    return HttpResponse("Story not found", status=404)

