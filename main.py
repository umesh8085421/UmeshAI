__version__ = "2.0.0"

import os
import json
import threading
import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
REQUEST_CODE = 731

FONT_FILE = os.path.join(
    os.path.dirname(__file__),
    "NotoSansDevanagari-Regular.ttf"
)

FONT_NAME = "HindiFont"

if os.path.exists(FONT_FILE):
    LabelBase.register(name=FONT_NAME, fn_regular=FONT_FILE)
else:
    FONT_NAME = "Roboto"


class UmeshAIApp(App):

    def build(self):
        self.title = "Umesh AI"
        self.request_lock = threading.Lock()
        self.android_voice_ready = False

        # These files are stored inside Android's private app-data folder.
        # The API key is not encrypted; it is kept in app-private storage.
        self.key_path = os.path.join(self.user_data_dir, "api_key.txt")
        self.history_path = os.path.join(
            self.user_data_dir, "chat_history.json"
        )

        self.history = [{
            "role": "system",
            "content": (
                "You are Umesh AI, a helpful assistant. "
                "Reply in the user's language, including Hindi. "
                "Be friendly, clear and helpful."
            )
        }]
        self.load_history()

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8)
        )

        heading = Label(
            text="[b]UMESH AI[/b]\nआपका अपना AI सहायक",
            markup=True,
            font_name=FONT_NAME,
            size_hint_y=None,
            height=dp(75),
            font_size="22sp",
            color=(0.25, 0.75, 1, 1)
        )
        root.add_widget(heading)

        key_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            spacing=dp(6)
        )

        self.key_input = TextInput(
            hint_text="Groq API Key यहाँ डालें",
            password=True,
            multiline=False,
            font_name=FONT_NAME
        )
        self.key_input.text = self.load_api_key()
        self.key_input.bind(focus=self.on_key_focus)
        key_row.add_widget(self.key_input)

        save_key_button = Button(
            text="सेव करें",
            font_name=FONT_NAME,
            size_hint_x=None,
            width=dp(90)
        )
        save_key_button.bind(on_press=self.save_api_key)
        key_row.add_widget(save_key_button)

        clear_key_button = Button(
            text="हटाएँ",
            font_name=FONT_NAME,
            size_hint_x=None,
            width=dp(70)
        )
        clear_key_button.bind(on_press=self.clear_api_key)
        key_row.add_widget(clear_key_button)
        root.add_widget(key_row)

        self.chat_label = Label(
            text="",
            font_name=FONT_NAME,
            size_hint_y=None,
            markup=True,
            halign="left",
            valign="top"
        )
        self.chat_label.bind(texture_size=self._resize_chat)

        scroll = ScrollView()
        scroll.add_widget(self.chat_label)
        root.add_widget(scroll)
        self.scroll = scroll
        self.refresh_chat()

        self.message_input = TextInput(
            hint_text="यहाँ अपना सवाल लिखें...",
            font_name=FONT_NAME,
            multiline=True,
            size_hint_y=None,
            height=dp(85)
        )
        root.add_widget(self.message_input)

        controls = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            spacing=dp(8)
        )

        mic = Button(
            text="बोलकर पूछें",
            font_name=FONT_NAME,
            background_color=(0.15, 0.55, 0.35, 1)
        )
        mic.bind(on_press=self.start_listening)
        controls.add_widget(mic)

        send = Button(
            text="भेजें",
            font_name=FONT_NAME,
            background_color=(0.12, 0.48, 0.85, 1)
        )
        send.bind(on_press=self.send_message)
        controls.add_widget(send)
        root.add_widget(controls)

        self.status = Label(
            text="तैयार है",
            font_name=FONT_NAME,
            size_hint_y=None,
            height=dp(35)
        )
        root.add_widget(self.status)

        return root

    def load_api_key(self):
        try:
            if os.path.isfile(self.key_path):
                with open(self.key_path, "r", encoding="utf-8") as file:
                    return file.read().strip()
        except Exception:
            pass
        return ""

    def save_api_key(self, *_):
        key = self.key_input.text.strip()
        if not key:
            self.status.text = "पहले API Key डालें।"
            return

        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.key_path, "w", encoding="utf-8") as file:
                file.write(key)
            try:
                os.chmod(self.key_path, 0o600)
            except Exception:
                pass
            self.status.text = "API Key इस फोन में सेव हो गई है।"
        except Exception as exc:
            self.status.text = "API Key सेव नहीं हुई: " + str(exc)

    def on_key_focus(self, instance, focused):
        if not focused and instance.text.strip():
            self.save_api_key()

    def clear_api_key(self, *_):
        try:
            if os.path.exists(self.key_path):
                os.remove(self.key_path)
            self.key_input.text = ""
            self.status.text = "सेव की गई API Key हटा दी गई है।"
        except Exception as exc:
            self.status.text = "Key नहीं हटाई जा सकी: " + str(exc)

    def load_history(self):
        try:
            if os.path.isfile(self.history_path):
                with open(self.history_path, "r", encoding="utf-8") as file:
                    saved = json.load(file)
                if isinstance(saved, list):
                    valid = [
                        item for item in saved
                        if isinstance(item, dict)
                        and item.get("role") in ("user", "assistant")
                        and isinstance(item.get("content"), str)
                    ]
                    self.history.extend(valid[-100:])
        except Exception:
            pass

    def save_history(self):
        try:
            saved = [
                item for item in self.history
                if item.get("role") in ("user", "assistant")
            ][-100:]
            with open(self.history_path, "w", encoding="utf-8") as file:
                json.dump(saved, file, ensure_ascii=False)
        except Exception:
            pass

    def refresh_chat(self):
        lines = []
        for item in self.history:
            role = item.get("role")
            if role == "user":
                who = "आप"
            elif role == "assistant":
                who = "Umesh AI"
            else:
                continue
            safe = str(item.get("content", "")).replace("[", "(").replace("]", ")")
            lines.append(f"[b]{who}:[/b] {safe}")

        self.chat_label.text = "\n\n".join(lines)
        self.chat_label.texture_update()
        self.chat_label.height = max(
            self.chat_label.texture_size[1], dp(300)
        )

    def on_start(self):
        try:
            from android import activity
            activity.bind(on_activity_result=self.on_activity_result)
            self.android_voice_ready = True
        except Exception:
            self.android_voice_ready = False
            self.status.text = "Voice सुविधा Android APK में उपलब्ध होगी।"

    def on_stop(self):
        if hasattr(self, "key_input") and self.key_input.text.strip():
            self.save_api_key()
        self.save_history()

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
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN")
            intent.putExtra(
                RecognizerIntent.EXTRA_PROMPT,
                "Umesh AI से अपना सवाल बोलिए"
            )

            self.status.text = "सुन रहा हूँ..."
            PythonActivity.mActivity.startActivityForResult(
                intent, REQUEST_CODE
            )
        except Exception as exc:
            self.status.text = "Voice शुरू नहीं हुआ।"
            self.add_chat("जानकारी", "Android Voice सेवा में समस्या: " + str(exc))

    def on_activity_result(self, request_code, result_code, intent):
        if request_code != REQUEST_CODE:
            return

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
                            self.status, "text", "आवाज़ समझ नहीं आई।"
                        )
                    )
            except Exception as exc:
                error_text = str(exc)
                Clock.schedule_once(
                    lambda dt: self.show_error(error_text)
                )
        else:
            Clock.schedule_once(
                lambda dt: setattr(self.status, "text", "Voice रद्द हुआ।")
            )

    def put_recognized_text(self, spoken_text):
        self.message_input.text = spoken_text
        self.status.text = "सवाल लिख दिया गया है। भेजें दबाएँ।"

    def send_message(self, *_):
        api_key = self.key_input.text.strip()
        message = self.message_input.text.strip()

        if not api_key:
            self.status.text = "पहले Groq API Key डालें।"
            return
        if not message:
            self.status.text = "पहले अपना सवाल लिखें।"
            return

        self.save_api_key()
        self.message_input.text = ""

        with self.request_lock:
            self.history.append({"role": "user", "content": message})
            messages_for_request = list(self.history)
        self.save_history()
        self.add_chat("आप", message)
        self.status.text = "Umesh AI सोच रहा है..."

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
                    "role": "assistant",
                    "content": answer
                })
            self.save_history()
            Clock.schedule_once(lambda dt: self.show_answer(answer))

        except Exception as exc:
            error_text = str(exc)
            Clock.schedule_once(lambda dt: self.show_error(error_text))

    def show_answer(self, answer):
        self.add_chat("Umesh AI", answer)
        self.status.text = "तैयार है"
        try:
            from plyer import tts
            tts.speak(answer)
        except Exception:
            self.status.text = "जवाब आ गया। आवाज़ की सेवा उपलब्ध नहीं है।"

    def show_error(self, error):
        self.add_chat("Error", error)
        self.status.text = "Internet या API Key जाँचें।"


if __name__ == "__main__":
    UmeshAIApp().run()
