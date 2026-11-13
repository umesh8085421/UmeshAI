__version__ = "3.0.0"

import os
import re
import json
import threading
import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.utils import get_color_from_hex
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
REQUEST_CODE = 731

# Keep this font file in the same GitHub folder as main.py.
FONT_FILE = os.path.join(os.path.dirname(__file__), "NotoSansDevanagari-Regular.ttf")
FONT_NAME = "Roboto"
if os.path.isfile(FONT_FILE):
    try:
        LabelBase.register(name="HindiFont", fn_regular=FONT_FILE)
        FONT_NAME = "HindiFont"
    except Exception:
        pass


def clean_answer(value):
    """Remove common Markdown decorations from the visible chat text."""
    text = str(value or "")
    text = re.sub(r"```(?:[a-zA-Z0-9_+-]+)?\s*", "", text)
    text = text.replace("```", "")
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)
    return text.strip()


class ChatBubble(BoxLayout):
    def __init__(self, speaker, message, mine=False, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            padding=(dp(12), dp(9)),
            spacing=dp(5),
            **kwargs
        )
        self.bind(minimum_height=self.setter("height"))
        bg = (0.07, 0.29, 0.23, 1) if mine else (0.13, 0.17, 0.24, 1)
        with self.canvas.before:
            Color(*bg)
            self.bg_rect = RoundedRectangle(radius=[dp(14)])
        self.bind(pos=self.update_bg, size=self.update_bg)

        heading = Label(
            text=speaker,
            font_name=FONT_NAME,
            font_size="13sp",
            bold=True,
            color=(0.53, 0.88, 1, 1) if not mine else (0.60, 0.98, 0.72, 1),
            size_hint_y=None,
            height=dp(22),
            halign="left",
            valign="middle"
        )
        heading.bind(size=lambda obj, val: setattr(obj, "text_size", val))

        body = Label(
            text=message,
            font_name=FONT_NAME,
            font_size="16sp",
            color=(0.95, 0.97, 1, 1),
            size_hint_y=None,
            halign="left",
            valign="top"
        )
        body.bind(width=lambda obj, val: setattr(obj, "text_size", (val, None)))
        body.bind(texture_size=lambda obj, val: setattr(obj, "height", val[1] + dp(6)))
        self.add_widget(heading)
        self.add_widget(body)

    def update_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class UmeshAIApp(App):
    def build(self):
        self.title = "Umesh AI"
        self.request_lock = threading.Lock()
        self.busy = False
        self.key_path = os.path.join(self.user_data_dir, "api_key.txt")
        self.history_path = os.path.join(self.user_data_dir, "chat_history.json")

        self.history = [{
            "role": "system",
            "content": (
                "You are Umesh AI, a helpful Hindi-first assistant. "
                "Reply in the user's language. Use clear, simple text. "
                "Avoid unnecessary Markdown and emojis."
            )
        }]
        self.load_history()

        root = BoxLayout(
            orientation="vertical",
            padding=(dp(12), dp(10)),
            spacing=dp(9)
        )
        with root.canvas.before:
            Color(*get_color_from_hex("#09111F"))
            self.root_bg = RoundedRectangle(pos=root.pos, size=root.size)
        root.bind(pos=self.update_root_bg, size=self.update_root_bg)

        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(66),
            spacing=dp(1)
        )
        header.add_widget(Label(
            text="[b]UMESH AI[/b]",
            markup=True,
            font_name=FONT_NAME,
            font_size="25sp",
            color=get_color_from_hex("#55C7FF")
        ))
        header.add_widget(Label(
            text="आपका अपना AI सहायक",
            font_name=FONT_NAME,
            font_size="14sp",
            color=get_color_from_hex("#B8C7D9")
        ))
        root.add_widget(header)

        key_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.key_input = TextInput(
            hint_text="Groq API Key यहाँ डालें",
            password=True,
            multiline=False,
            font_name=FONT_NAME,
            font_size="14sp",
            padding=(dp(10), dp(12)),
            background_normal="",
            background_active="",
            background_color=get_color_from_hex("#E8EEF5"),
            foreground_color=get_color_from_hex("#152235"),
            cursor_color=get_color_from_hex("#152235")
        )
        self.key_input.text = self.load_api_key()
        self.key_input.bind(focus=self.on_key_focus)
        key_row.add_widget(self.key_input)
        save_btn = self.make_button("सेव", "#34445B", width=dp(62))
        save_btn.bind(on_release=self.save_api_key)
        key_row.add_widget(save_btn)
        clear_btn = self.make_button("हटाएँ", "#34445B", width=dp(66))
        clear_btn.bind(on_release=self.clear_api_key)
        key_row.add_widget(clear_btn)
        root.add_widget(key_row)

        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        self.chat_stack = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=(dp(2), dp(8))
        )
        self.chat_stack.bind(minimum_height=self.chat_stack.setter("height"))
        self.scroll.add_widget(self.chat_stack)
        root.add_widget(self.scroll)
        self.refresh_chat()

        self.message_input = TextInput(
            hint_text="अपना सवाल यहाँ लिखें...",
            font_name=FONT_NAME,
            font_size="16sp",
            foreground_color=get_color_from_hex("#142033"),
            hint_text_color=get_color_from_hex("#68778A"),
            cursor_color=get_color_from_hex("#142033"),
            background_normal="",
            background_active="",
            background_color=get_color_from_hex("#F1F5F9"),
            padding=(dp(12), dp(10)),
            multiline=True,
            size_hint_y=None,
            height=dp(82)
        )
        root.add_widget(self.message_input)

        controls = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        mic_btn = self.make_button("🎙 बोलकर पूछें", "#087A55")
        mic_btn.bind(on_release=self.start_listening)
        controls.add_widget(mic_btn)
        send_btn = self.make_button("भेजें", "#1769B2")
        send_btn.bind(on_release=self.send_message)
        controls.add_widget(send_btn)
        root.add_widget(controls)

        self.status = Label(
            text="तैयार है",
            font_name=FONT_NAME,
            font_size="12sp",
            color=get_color_from_hex("#A9B8CA"),
            size_hint_y=None,
            height=dp(24)
        )
        root.add_widget(self.status)
        return root

    def update_root_bg(self, instance, *_):
        self.root_bg.pos = instance.pos
        self.root_bg.size = instance.size

    def make_button(self, text, color, width=None):
        return Button(
            text=text,
            font_name=FONT_NAME,
            font_size="15sp",
            bold=True,
            background_normal="",
            background_down="",
            background_color=get_color_from_hex(color),
            color=(1, 1, 1, 1),
            size_hint_x=None if width else 1,
            width=width or 0
        )

    def load_api_key(self):
        try:
            with open(self.key_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    def save_api_key(self, *_):
        key = self.key_input.text.strip()
        if not key:
            self.status.text = "पहले API Key डालें।"
            return
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.key_path, "w", encoding="utf-8") as f:
                f.write(key)
            try:
                os.chmod(self.key_path, 0o600)
            except Exception:
                pass
            self.status.text = "API Key सेव हो गई है।"
        except Exception as exc:
            self.status.text = "Key सेव नहीं हुई: " + str(exc)

    def on_key_focus(self, instance, focused):
        if not focused and instance.text.strip():
            self.save_api_key()

    def clear_api_key(self, *_):
        try:
            if os.path.exists(self.key_path):
                os.remove(self.key_path)
            self.key_input.text = ""
            self.status.text = "API Key हटा दी गई है।"
        except Exception as exc:
            self.status.text = "Key नहीं हट सकी: " + str(exc)

    def load_history(self):
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, list):
                for item in saved[-80:]:
                    if (isinstance(item, dict)
                        and item.get("role") in ("user", "assistant")
                        and isinstance(item.get("content"), str)):
                        self.history.append(item)
        except Exception:
            pass

    def save_history(self):
        try:
            saved = [
                item for item in self.history
                if item.get("role") in ("user", "assistant")
            ][-80:]
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(saved, f, ensure_ascii=False)
        except Exception:
            pass

    def refresh_chat(self):
        self.chat_stack.clear_widgets()
        for item in self.history:
            role = item.get("role")
            if role == "user":
                self.add_bubble("आप", item.get("content", ""), True, False)
            elif role == "assistant":
                self.add_bubble("Umesh AI", clean_answer(item.get("content", "")), False, False)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.2)

    def add_bubble(self, who, message, mine=False, scroll=True):
        bubble = ChatBubble(who, clean_answer(message), mine=mine)
        bubble.size_hint_x = 1
        self.chat_stack.add_widget(bubble)
        if scroll:
            Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.15)

    def on_start(self):
        try:
            from android import activity
            activity.bind(on_activity_result=self.on_activity_result)
        except Exception:
            self.status.text = "Voice सुविधा Android APK में उपलब्ध होगी।"

    def on_stop(self):
        if hasattr(self, "key_input") and self.key_input.text.strip():
            self.save_api_key()
        self.save_history()

    def start_listening(self, *_):
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN")
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "hi-IN")
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "अपना सवाल बोलिए")
            self.status.text = "सुन रहा हूँ..."
            PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE)
        except Exception as exc:
            self.status.text = "माइक्रोफोन शुरू नहीं हुआ: " + str(exc)

    def on_activity_result(self, request_code, result_code, intent):
        if request_code != REQUEST_CODE:
            return
        if result_code == -1 and intent is not None:
            try:
                from jnius import autoclass
                RecognizerIntent = autoclass("android.speech.RecognizerIntent")
                results = intent.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                if results and results.size() > 0:
                    spoken = str(results.get(0))
                    Clock.schedule_once(lambda dt: self.on_voice_text(spoken))
                else:
                    Clock.schedule_once(lambda dt: setattr(self.status, "text", "आवाज़ समझ नहीं आई।"))
            except Exception as exc:
                msg = str(exc)
                Clock.schedule_once(lambda dt: setattr(self.status, "text", "Voice error: " + msg))
        else:
            Clock.schedule_once(lambda dt: setattr(self.status, "text", "Voice रद्द हुआ।"))

    def on_voice_text(self, spoken):
        self.message_input.text = spoken
        self.status.text = "आपका सवाल मिला — भेज रहा हूँ..."
        # Automatically send recognized speech. Typed messages still use Send.
        Clock.schedule_once(self.send_message, 0.35)

    def send_message(self, *_):
        if self.busy:
            self.status.text = "पहले मौजूदा जवाब पूरा होने दें।"
            return
        api_key = self.key_input.text.strip()
        message = self.message_input.text.strip()
        if not api_key:
            self.status.text = "पहले Groq API Key डालें।"
            return
        if not message:
            self.status.text = "पहले अपना सवाल लिखें या बोलें।"
            return

        self.save_api_key()
        self.message_input.text = ""
        with self.request_lock:
            self.history.append({"role": "user", "content": message})
            request_history = list(self.history)
        self.save_history()
        self.add_bubble("आप", message, True)
        self.busy = True
        self.status.text = "Umesh AI जवाब तैयार कर रहा है..."
        threading.Thread(
            target=self.call_api,
            args=(api_key, request_history),
            daemon=True
        ).start()

    def call_api(self, api_key, request_history):
        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": request_history,
                    "temperature": 0.6,
                    "max_tokens": 1200
                },
                timeout=60
            )
            if response.status_code != 200:
                detail = response.text[:500]
                Clock.schedule_once(lambda dt: self.show_error(
                    "API Error " + str(response.status_code) + ": " + detail
                ))
                return
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            with self.request_lock:
                self.history.append({"role": "assistant", "content": answer})
            self.save_history()
            Clock.schedule_once(lambda dt: self.show_answer(answer))
        except Exception as exc:
            msg = str(exc)
            Clock.schedule_once(lambda dt: self.show_error(msg))

    def show_answer(self, answer):
        self.busy = False
        cleaned = clean_answer(answer)
        self.add_bubble("Umesh AI", cleaned, False)
        self.status.text = "तैयार है"
        try:
            from plyer import tts
            tts.speak(cleaned)
        except Exception:
            self.status.text = "जवाब आ गया।"

    def show_error(self, error):
        self.busy = False
        self.add_bubble("समस्या", error, False)
        self.status.text = "इंटरनेट या API Key जाँचें।"


if __name__ == "__main__":
    UmeshAIApp().run()
