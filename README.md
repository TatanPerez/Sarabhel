# Sarabhel

Proyecto de hackathon para construir un C2 basico usando Supabase, n8n y un agente en Python.

El sistema usa Supabase como plano de control: los agentes se registran, envian heartbeat, reciben tareas pendientes y devuelven el resultado de los comandos ejecutados. n8n funciona como consola operativa y automatizacion para crear tareas, marcar agentes inactivos y generar reportes.

> Uso previsto: laboratorio, demo o entorno autorizado. El agente ejecuta comandos del sistema operativo con `shell=True`, por lo que no debe usarse contra maquinas o redes sin permiso explicito.

## Componentes

| Ruta | Descripcion |
| --- | --- |
| `Agentes/agent.py` | Agente Python que se registra en Supabase, envia heartbeat cada 5 segundos, consulta tareas pendientes y ejecuta comandos asignados. |
| `Supabase/supabase.sql` | Esquema de base de datos con las tablas `agents` y `tasks`. |
| `N8N/C2-Aligo-N8N.json` | Workflow de n8n para operar el C2 desde formulario, tareas programadas y reportes PDF. |

## Arquitectura

1. El agente se conecta a Supabase con `SUPABASE_URL` y `SUPABASE_KEY`.
2. Al iniciar, registra o reconecta su fila en la tabla `agents`.
3. Cada 5 segundos actualiza `last_heartbeat`, guarda un `last_output` basico y busca tareas en `tasks` con estado `pending`.
4. Si encuentra una tarea asignada a su `agent_id`, cambia su estado a `running`, ejecuta el comando y actualiza la tarea como `completed` o `failed`.
5. n8n permite crear tareas desde un formulario, limpiar estados de agentes sin heartbeat reciente y generar reportes.

## Esquema de datos

### `agents`

Registra los agentes disponibles.

Campos principales:

- `id`: UUID del agente.
- `name`: nombre visible del agente.
- `role`: rol del agente, por ejemplo `collector`, `executor`, `relay` o `monitor`.
- `status`: estado actual, por defecto `offline`.
- `last_heartbeat`: ultima marca de vida del agente.
- `last_output`: ultimo resultado reportado por el agente.

### `tasks`

Registra comandos a ejecutar por agentes.

Campos principales:

- `id`: UUID de la tarea.
- `agent_id`: UUID del agente asignado.
- `command`: comando que se ejecutara.
- `status`: `pending`, `running`, `completed` o `failed`.
- `output`: salida estandar o error devuelto por el comando.

## Configuracion

### 1. Supabase

1. Crea un proyecto en Supabase.
2. Ejecuta el esquema de `Supabase/supabase.sql` en el editor SQL.
3. Obtiene la URL del proyecto y una API key valida.
4. Verifica que las tablas `agents` y `tasks` existan en el esquema `public`.

### 2. Agente Python

Instala la dependencia principal:

```bash
pip install supabase
```

Edita `Agentes/agent.py` y reemplaza los placeholders:

```python
SUPABASE_URL = "URL_DE_SUPABASE"
SUPABASE_KEY = "CLAVE_DE_SUPABASE"
```

Tambien puedes ajustar la identidad del agente:

```python
AGENT_ID = "11111111-1111-1111-1111-111111111111"
AGENT_NAME = "Agente-Python-01"
AGENT_ROLE = "executor"
```

Ejecuta el agente:

```bash
python Agentes/agent.py
```

Para detenerlo, usa `Ctrl+C`. El script intentara cambiar el estado del agente a `offline` antes de salir.

### 3. n8n

Importa `N8N/C2-Aligo-N8N.json` en n8n y configura las credenciales requeridas:

- Supabase API para crear tareas y consultar agentes.
- Postgres para ejecutar la consulta que marca agentes inactivos como `offline`.
- HTML/CSS to PDF para convertir el reporte HTML a PDF.

El workflow incluye:

- Formulario `Consola Operador C2- Aligo` para crear filas en `tasks`.
- Tarea programada cada minuto que marca como `offline` los agentes `online` cuyo `last_heartbeat` sea anterior a 30 segundos.
- Tarea programada diaria que consulta `agents`, genera HTML y lo convierte a PDF.

## Operacion basica

1. Inicia el agente Python.
2. Confirma en Supabase que el agente aparece en `agents` con estado `online`.
3. Desde n8n o Supabase, crea una tarea en `tasks` con:
   - `agent_id`: UUID del agente.
   - `command`: comando a ejecutar.
   - `status`: `pending`.
4. Espera el ciclo de polling del agente.
5. Revisa `tasks.output`, `tasks.status` y `agents.last_output`.

Ejemplo de tarea:

```sql
INSERT INTO tasks (agent_id, command, status)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'whoami',
  'pending'
);
```

## Consideraciones de seguridad

- No uses credenciales reales hardcodeadas en repositorios publicos.
- Restringe los permisos de Supabase y n8n al minimo necesario.
- Ejecuta el agente solo en maquinas de prueba o entornos autorizados.
- Valida o limita los comandos aceptados antes de usarlo fuera de una demo.
- Revisa politicas de Row Level Security si el proyecto se expone a usuarios externos.

## Estado actual

El repositorio contiene una prueba funcional de concepto:

- Agente Python con heartbeat y ejecucion de tareas.
- Esquema Supabase para agentes y tareas.
- Workflow n8n para consola, mantenimiento de estado y reporte.

