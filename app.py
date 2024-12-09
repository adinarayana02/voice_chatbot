import os
import io
import logging
import requests
from flask import Flask, render_template, request, jsonify, send_file
import pyttsx3
import speech_recognition as sr

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Groq API configuration
API_KEY = "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"
MODEL = "llama3-8b-8192"

# Conversational context storage
conversation_history = []
MAX_CONVERSATION_HISTORY = 5


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        # Check if audio file is in the request
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file'}), 400

        # Get the audio file
        audio_file = request.files['audio']

        # Use SpeechRecognition to transcribe
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)

        return jsonify({'transcription': text})

    except sr.UnknownValueError:
        return jsonify({'error': 'Could not understand audio'}), 400
    except sr.RequestError as e:
        logger.error(f"Speech recognition error: {e}")
        return jsonify({'error': 'Speech recognition service error'}), 500
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return jsonify({'error': 'Unexpected error during transcription'}), 500


@app.route('/generate', methods=['POST'])
def generate_response():
    try:
        # Get user input text
        user_text = request.json.get('text', '').strip()

        if not user_text:
            return jsonify({'error': 'No input text provided'}), 400

        # Manage conversation history
        conversation_history.append({"role": "user", "content": user_text})

        # Limit conversation history
        if len(conversation_history) > MAX_CONVERSATION_HISTORY:
            conversation_history.pop(0)

        # Prepare messages for API call (include system prompt and conversation history)
        messages = [
                       {"role": "system",
                        "content": "You are a helpful, articulate, and friendly AI assistant. Provide clear, concise, and informative responses."}
                   ] + conversation_history

        # Call Groq API for response
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.7,  # Add some creativity
                    "max_tokens": 300,  # Limit response length
                }
            )
            response.raise_for_status()  # Raise an exception for bad responses
        except requests.RequestException as e:
            logger.error(f"API request error: {e}")
            return jsonify({'error': 'Failed to connect to AI service'}), 500

        # Extract response text
        try:
            response_data = response.json()
            ai_response = response_data['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError) as e:
            logger.error(f"Response parsing error: {e}")
            return jsonify({'error': 'Failed to parse AI response'}), 500

        # Add AI response to conversation history
        conversation_history.append({"role": "assistant", "content": ai_response})

        # Generate audio for the response using pyttsx3
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')

            # Set an Indian female voice
            for voice in voices:
                if "Indian" in voice.name and "Female" in voice.name:
                    engine.setProperty('voice', voice.id)
                    break

            engine.setProperty('rate', 150)  # Set speaking rate
            audio_file = "response.mp3"
            engine.save_to_file(ai_response, audio_file)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"Text-to-speech error: {e}")
            # Continue without audio if TTS fails
            audio_file = None

        # Return response with audio path
        return jsonify({
            'text': ai_response,
            'audio_url': f'/download_audio/{audio_file}' if audio_file else None
        })

    except Exception as e:
        logger.error(f"Unexpected error in generate_response: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@app.route('/download_audio/<filename>', methods=['GET'])
def download_audio(filename):
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error serving audio file: {e}")
        return jsonify({'error': 'Error retrieving audio file'}), 500


@app.route('/reset', methods=['POST'])
def reset_conversation():
    global conversation_history
    conversation_history.clear()
    return jsonify({'status': 'Conversation reset successfully'})


if __name__ == '__main__':
    app.run(debug=True)
