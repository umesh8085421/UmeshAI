# Umesh AI Android app project

## Features
- Kivy chat interface
- Groq Chat Completions API
- Hindi/English assistant
- API key entered at runtime; it is not embedded in the APK or saved to disk

## Test on a computer
Install Python, Kivy and requests, then run:
    pip install kivy requests
    python main.py

## Build APK
Buildozer's Android toolchain requires Linux or macOS (Windows users can use WSL).
This project includes a GitHub Actions workflow:
1. Create a GitHub repository named `UmeshAI`.
2. Upload all files and folders from this project to the repository.
3. Open the repository's Actions tab.
4. Run "Build Umesh AI APK" using "Run workflow" (or push to main).
5. When it finishes, open the workflow run and download the `UmeshAI-debug-apk` artifact.
6. Extract the ZIP and install the APK on your Android phone. Android may ask permission to install unknown apps.

## Security
- Do not share your Groq API key.
- The app asks for the key each time it starts and keeps it in memory only.
- This is a personal prototype. For a public app, route requests through your own secure backend; never distribute a shared API key inside an APK.

## Model
Default model: `openai/gpt-oss-120b`. If Groq changes availability, check the current model list at:
https://console.groq.com/docs/models
