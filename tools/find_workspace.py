import glob

for f in glob.glob('/app/build/_app/immutable/**/*.js', recursive=True):
    try:
        txt = open(f, encoding='utf-8', errors='ignore').read()
        idx = txt.find('id="sidebar"')
        if idx != -1:
            snippet = txt[idx: idx + 600]
            print(snippet)
            break
    except Exception:
        pass

