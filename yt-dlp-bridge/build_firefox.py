#!/usr/bin/env python3
"""Build extension-firefox/ : same extension, with a Firefox-style manifest.

Chrome/Brave/Edge use a service worker; Firefox wants background.scripts.
Run once, then in Firefox load extension-firefox/manifest.json via
about:debugging#/runtime/this-firefox -> Load Temporary Add-on.
"""
import json, os, shutil

root = os.path.dirname(os.path.abspath(__file__))
src, dst = os.path.join(root, "extension"), os.path.join(root, "extension-firefox")
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst)
path = os.path.join(dst, "manifest.json")
m = json.load(open(path))
m.pop("key", None)
m["background"] = {"scripts": ["background.js"]}
m["browser_specific_settings"] = {"gecko": {"id": "yt-dlp-bridge@local", "strict_min_version": "128.0"}}
json.dump(m, open(path, "w"), indent=2)
print("Built", dst)
