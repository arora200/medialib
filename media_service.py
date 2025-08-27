import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import os
import logging

# Add the project directory to the Python path
# This is crucial so that 'app' and 'models' can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.append(project_root)

# Configure logging for the service
# This log file will capture output from the service itself
logging.basicConfig(
    filename=os.path.join(project_root, 'media_service.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MediaFlaskService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MediaFlaskService"
    _svc_display_name_ = "Media Library Flask Application"
    _svc_description_ = "Runs the Flask-based Media Library application as a Windows service."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True
        self.app = None
        self.server_thread = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logging.info("MediaFlaskService: Stopping service...")
        self.is_running = False
        win32event.SetEvent(self.hWaitStop)
        # Attempt to gracefully shut down the Flask server
        if self.app:
            try:
                # This is a hacky way to shut down Flask's dev server
                # For production, use a WSGI server like Gunicorn/Waitress
                # that has proper shutdown mechanisms.
                func = request.environ.get('werkzeug.server.shutdown')
                if func is None:
                    raise RuntimeError('Not running with the Werkzeug Server')
                func()
                logging.info("Werkzeug server shutdown initiated.")
            except Exception as e:
                logging.error(f"Error during Werkzeug server shutdown: {e}")
        logging.info("MediaFlaskService: Service stopped.")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        logging.info("MediaFlaskService: Service started.")

        try:
            from app import app, init_db # Import your Flask app and init_db function
            from threading import Thread
            from flask import request # Import request for shutdown hack

            # Initialize the database within the app context
            with app.app_context():
                init_db()
                logging.info("Database initialized.")

            # Run the Flask app in a separate thread
            # Note: For production, use a production-ready WSGI server (e.g., Waitress, Gunicorn)
            # app.run() is for development only.
            def run_flask_app():
                try:
                    app.run(host='0.0.0.0', port=5000, debug=False) # debug=False for service
                except Exception as e:
                    logging.error(f"Error running Flask app: {e}")

            self.server_thread = Thread(target=run_flask_app)
            self.server_thread.daemon = True # Daemonize thread so it exits with main thread
            self.server_thread.start()
            logging.info("Flask app started in a separate thread.")

            # Keep the service running until stop event is set
            while self.is_running:
                win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

        except Exception as e:
            logging.error(f"MediaFlaskService: Unhandled exception in SvcDoRun: {e}")
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_ERROR_TYPE,
                servicemanager.PYS_SERVICE_ERROR,
                (str(e), '')
            )

def main():
    if len(sys.argv) == 1:
        servicemanager.Initialize('MediaFlaskService', MediaFlaskService)
        servicemanager.PrepareToHostSingle(MediaFlaskService)
        servicemanager.StopService()
    else:
        win32serviceutil.HandleCommandLine(MediaFlaskService)

if __name__ == '__main__':
    main()
