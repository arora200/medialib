import shutil
import os
from datetime import datetime
import subprocess # For service control

# --- Configuration ----
APP_ROOT = r'E:\AppDevelopment\medialib' # Your application's root directory
MEDIA_LIBRARY_PATH = os.path.join(APP_ROOT, 'media_library')
MEDIA_DB_PATH = os.path.join(APP_ROOT, 'instance', 'media.db')
BACKUP_DESTINATION_ROOT = r'D:\mediabackups' # Where backups will be stored
SERVICE_NAME = 'MedialibService' # The name of your Windows service (if applicable)

def stop_service(service_name):
    print(f"Stopping service: {service_name}...")
    # Use shell=True for net stop/start commands on Windows
    subprocess.run(['net', 'stop', service_name], check=True, shell=True)
    print(f"Service {service_name} stopped.")

def start_service(service_name):
    print(f"Starting service: {service_name}...")
    # Use shell=True for net stop/start commands on Windows
    subprocess.run(['net', 'start', service_name], check=True, shell=True)
    print(f"Service {service_name} started.")

def perform_backup():
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir = os.path.join(BACKUP_DESTINATION_ROOT, timestamp)

    try:
        os.makedirs(backup_dir, exist_ok=True)
        print(f"Created backup directory: {backup_dir}")

        # --- Stop Service (if running as one) ---
        # Uncomment the following lines if you are running the app as a Windows service
        # and want to stop it during backup. Requires script to be run with Administrator privileges.
        # try:
        #     stop_service(SERVICE_NAME)
        # except subprocess.CalledProcessError:
        #     print(f"Service {SERVICE_NAME} not running or failed to stop. Proceeding with backup.")

        # --- Copy media.db ---
        db_backup_path = os.path.join(backup_dir, 'media.db')
        shutil.copy2(MEDIA_DB_PATH, db_backup_path)
        print(f"Backed up {MEDIA_DB_PATH} to {db_backup_path}")

        # --- Copy media_library folder ---
        media_library_backup_path = os.path.join(backup_dir, 'media_library')
        shutil.copytree(MEDIA_LIBRARY_PATH, media_library_backup_path)
        print(f"Backed up {MEDIA_LIBRARY_PATH} to {media_library_backup_path}")

        print("Backup completed successfully!")

    except Exception as e:
        print(f"Backup failed: {e}")
    finally:
        # --- Start Service (if stopped) ---
        # Uncomment the following lines if you stopped the service for backup.
        # try:
        #     start_service(SERVICE_NAME)
        # except subprocess.CalledProcessError:
        #     print(f"Service {SERVICE_NAME} failed to start or was not stopped.")
        pass # Keep this pass if you don't uncomment service control

if __name__ == "__main__":
    perform_backup()
