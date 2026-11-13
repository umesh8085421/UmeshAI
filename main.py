__version__ = "1.1.0"

import threading
import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
REQUEST_CODE = 731


class UmeshAIApp(App):
    def build(self):
        self.title = "Umesh AI"
        self.history = [{
            "role": "system",
            "content": (
                "You are Umesh AI, a helpful assistant. "
                "Reply in the user's language, including Hindi."
            )
        }]
        self.request_lock = threading.Lock()
        self.android_voice_ready = False

        root = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(8)
        )

        heading = Label(
            text="[b]UMESH AI[/b]\nYour personal AI assistant",
            markup=True, size_hint_y=None, height=dp(64),
            font_size="22sp", color=(0.25, 0.75, 1, 1)
        )
        root.add_widget(heading)

        self.key_input = TextInput(
            hint_text="Paste your Groq API Key here",
            password=True, multiline=False,
            size_hint_y=None, height=dp(48)
        )
        root.add_widget(self.key_input)

        self.chat_label = Label(
            text="Namaste! Main Umesh AI hoon. API key daal kar message bhejein.",
            size_hint_y=None, markup=True, halign="left", valign="top"
        )
        self.chat_label.bind(texture_size=self._resize_chat)
        scroll = ScrollView()
        scroll.add_widget(self.chat_label)
        root.add_widget(scroll)
        self.scroll = scroll

        self.message_input = TextInput(
            hint_text="Yahan apna message likhein...",
            multiline=True, size_hint_y=None, height=dp(85)
        )
        root.add_widget(self.message_input)

        controls = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(50), spacing=dp(8)
        )

        mic = Button(
            text="🎤 Bolkar poochhein",
            background_color=(0.15, 0.55, 0.35, 1)
        )
        mic.bind(on_press=self.start_listening)
        controls.add_widget(mic)

        send = Button(
            text="Send",
            background_color=(0.12, 0.48, 0.85, 1)
        )
        send.bind(on_press=self.send_message)
        controls.add_widget(send)
        root.add_widget(controls)

        self.status = Label(
            text="Ready", size_hint_y=None, height=dp(28)
        )
        root.add_widget(self.status)

        return root

    def on_start(self):
        # Android speech recognition uses the phone's speech service.
        try:
            from android import activity
            activity.bind(on_activity_result=self.on_activity_result)
            self.android_voice_ready = True
        except Exception:
            self.android_voice_ready = False
            self.status.text = "Voice input is available in the Android APK."

    def _resize_chat(self, instance, size):
        if self.root:
            instance.text_size = (self.root.width - dp(36), None)
        instance.height = max(size[1], dp(300))

    def add_chat(self, who, message):
        safe = str(message).replace("[", "(").replace("]", ")")
        self.chat_label.text += f"\n\n[b]{who}:[/b] {safe}"
        self.chat_label.texture_update()
        self.chat_label.height = max(
            self.chat_label.texture_size[1], dp(300)
        )
        Clock.schedule_once(
            lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1
        )

    def start_listening(self, *_):
        try:
            from jnius import autoclass
            from android import activity

            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass(
                "android.speech.RecognizerIntent"
            )
            PythonActivity = autoclass(
                "org.kivy.android.PythonActivity"
            )

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE, "hi-IN"
            )
            intent.putExtra(
                RecognizerIntent.EXTRA_PROMPT,
                "Umesh AI se apna sawaal boliye"
            )

            self.status.text = "Sun raha hoon..."
            PythonActivity.mActivity.startActivityForResult(
                intent, REQUEST_CODE
            )
        except Exception as exc:
            self.status.text = "Voice input start nahi hua."
            self.add_chat(
                "Info",
                "Android APK mein RECORD_AUDIO permission aur "
                "pyjnius setup check karein. " + str(exc)
            )

    def on_activity_result(self, request_code, result_code, intent):
        if request_code != REQUEST_CODE:
            return

        # Android RESULT_OK is -1.
        if result_code == -1 and intent is not None:
            try:
                from jnius import autoclass
                RecognizerIntent = autoclass(
                    "android.speech.RecognizerIntent"
                )
                results = intent.getStringArrayListExtra(
                    RecognizerIntent.EXTRA_RESULTS
                )
                if results and results.size() > 0:
                    spoken_text = str(results.get(0))
                    Clock.schedule_once(
                        lambda dt: self.put_recognized_text(spoken_text)
                    )
                else:
                    Clock.schedule_once(
                        lambda dt: setattr(
                            self.status, "text", "Awaaz samajh nahi aayi."
                        )
                    )
            except Exception as exc:
                Clock.schedule_once(
                    lambda dt: self.show_error(str(exc))
                )
        else:
            Clock.schedule_once(
                lambda dt: setattr(self.status, "text", "Voice cancelled.")
            )

    def put_recognized_text(self, spoken_text):
        self.message_input.text = spoken_text
        self.status.text = "Aapka sawaal likh diya gaya hai. Send dabayein."

    def send_message(self, *_):
        api_key = self.key_input.text.strip()
        message = self.message_input.text.strip()

        if not api_key:
            self.status.text = "Pehle Groq API key daalein."
            return
        if not message:
            self.status.text = "Pehle apna sawaal likhein ya mic dabayein."
            return

        self.message_input.text = ""
        self.add_chat("You", message)

        with self.request_lock:
            self.history.append({"role": "user", "content": message})
            messages_for_request = list(self.history)

        self.status.text = "Umesh AI soch raha hai..."
        threading.Thread(
            target=self.call_api,
            args=(api_key, messages_for_request),
            daemon=True
        ).start()

    def call_api(self, api_key, messages_for_request):
        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": messages_for_request,
                    "temperature": 0.7,
                    "max_tokens": 1024
                },
                timeout=60
            )

            if response.status_code != 200:
                detail = response.text[:700]
                Clock.schedule_once(
                    lambda dt: self.show_error(
                        f"API Error {response.status_code}: {detail}"
                    )
                )
                return

            data = response.json()
            answer = data["choices"][0]["message"]["content"]

            with self.request_lock:
                self.history.append({
                    "role": "assistant", "content": answer
                })

            Clock.schedule_once(
                lambda dt: self.show_answer(answer)
            )

        except Exception as exc:
            Clock.schedule_once(
                lambda dt: self.show_error(str(exc))
            )

    def show_answer(self, answer):
        self.add_chat("Umesh AI", answer)
        self.status.text = "Ready"

        # Speak the AI answer aloud using the phone's text-to-speech engine.
        try:
            from plyer import tts
            tts.speak(answer)
        except Exception:
            self.status.text = (
                "Jawab aa gaya. Phone TTS service available nahi hai."
            )

    def show_error(self, error):
        self.add_chat("Error", error)
        self.status.text = "Please check internet/API key."


if __name__ == "__main__":
    UmeshAIApp().run()
