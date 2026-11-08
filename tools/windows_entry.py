"""Lanceur distribué : interpréteur inclus et calculs isolés compatibles Windows."""
import multiprocessing
import sys
import json
from threading import Timer
import webbrowser

if __name__=="__main__":
    multiprocessing.freeze_support()
    from bzhaventure.settings import PAGE, LOGO, REFERENCES, USER_ROOT, HOST, PORT
    if "--self-test" in sys.argv:
        import garminconnect
        from bzhaventure import __version__
        from bzhaventure.storage import Store
        store=Store()
        print(json.dumps(dict(version=__version__,python=sys.version,web=PAGE.is_file(),logo=LOGO.is_file(),
            examples=len(list(REFERENCES.glob("*.gpx"))),data=str(USER_ROOT),garmin=True)))
        sys.exit(0)
    if "--no-browser" not in sys.argv:Timer(.8,lambda:webbrowser.open(f"http://{HOST}:{PORT}")).start()
    from bzhaventure.server import main
    main()
