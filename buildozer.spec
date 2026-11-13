
[app]
title = Umesh AI
package.name = umeshai
package.domain = org.umeshai
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,otf
source.include_patterns = **/*.ttf,**/*.otf
version = 3.0.0
requirements = python3,kivy,requests,plyer,pillow
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,RECORD_AUDIO
android.api = 35
android.minapi = 24
android.ndk = 28c
android.accept_sdk_license = True
android.archs = arm64-v8a
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 0
