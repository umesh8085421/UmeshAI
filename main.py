__version__ = "1.0.0"

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


class UmeshAIApp(App):
    def build(self):
        self.title = "Umesh AI"
        self.history = [{
            "role": "system",
            "content": "You are Umesh AI, a helpful assistant. Reply in the user's language, including Hindi."
        }]

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        heading = Label(
            text="[b]UMESH AI[/b]\nYour personal AI assistant",
            markup=True, size_hint_y=None, height=dp(64),
            font_size="22sp", color=(0.25, 0.75, 1, 1)
        )
        root.add_widget(heading)

        self.key_input = TextInput(
            hint_text="Paste your Groq API Key here (kept only while app is open)",
            password=True, multiline=False, size_hint_y=None, height=dp(48)
        )
        root.add_widget(self.key_input)

        self.chat_label = Label(
            text="Namaste! Main Umesh AI hoon. Apna API key daal kar message bhejein.",
            size_hint_y=None, markup=True, halign="left", valign="top"
        )
        self.chat_label.bind(texture_size=self._resize_chat)
        scroll = ScrollView()
        scroll.add_widget(self.chat_label)
        root.add_widget(scroll)
        self.scroll = scroll

        self.message_input = TextInput(
            hint_text="Yahan apna message likhein...",
            multiline=True, size_hint_y=None, height=dp(90)
        )
        root.add_widget(self.message_input)

        send = Button(
            text="Send",
            size_hint_y=None, height=dp(50),
            background_color=(0.12, 0.48, 0.85, 1)
        )
        send.bind(on_press=self.send_message)
        root.add_widget(send)

        self.status = Label(text="Ready", size_hint_y=None, height=dp(28))
        root.add_widget(self.status)
        return root

    def _resize_chat(self, instance, size):
        instance.text_size = (self.root.width - dp(36), None)
        instance.height = max(size[1], dp(300))

    def add_chat(self, who, message):
        safe = str(message).replace("[", "(").replace("]", ")")
        self.chat_label.text += f"\n\n[b]{who}:[/b] {safe}"
        self.chat_label.texture_update()
        self.chat_label.height = max(self.chat_label.texture_size[1], dp(300))
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1)

    def send_message(self, *_):
        api_key = self.key_input.text.strip()
        message = self.message_input.text.strip()

        if not api_key:
            self.status.text = "Pehle Groq API key daalein."
            return
        if not message:
            return

        self.message_input.text = ""
        self.add_chat("You", message)
        self.history.append({"role": "user", "content": message})
        self.status.text = "Umesh AI soch raha hai..."
        threading.Thread(
            target=self.call_api, args=(api_key, message), daemon=True
        ).start()

    def call_api(self, api_key, message):
        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": self.history,
                    "temperature": 0.7,
                    "max_tokens": 1024
                },
                timeout=60
            )
            if response.status_code != 200:
                detail = response.text[:700]
                self.history.pop()
                Clock.schedule_once(
                    lambda dt: self.show_error(f"API Error {response.status_code}: {detail}")
                )
                return

            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            self.history.append({"role": "assistant", "content": answer})
            Clock.schedule_once(lambda dt: self.show_answer(answer))

        except Exception as exc:
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            Clock.schedule_once(lambda dt: self.show_error(str(exc)))

    def show_answer(self, answer):
        self.add_chat("Umesh AI", answer)
        self.status.text = "Ready"

    def show_error(self, error):
        self.add_chat("Error", error)
        self.status.text = "Please check internet/API key."


if __name__ == "__main__":
    UmeshAIApp().run()
