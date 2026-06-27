"""
Operator CLI – Command-line interface for interacting with the C2 server.

Commands:
- list-agents: Show all registered agents
- send: Dispatch a command to a specific agent
- watch: Stream results from an agent
- events: Monitor events in real time
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional

import click
import requests
from paho.mqtt import client as mqtt
from tabulate import tabulate

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
API_URL = os.getenv("C2_API_URL", "http://localhost:8000/api/v1")
API_KEY = os.getenv("C2_API_KEY", "supersecretapikey")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

HEADERS = {"X-API-Key": API_KEY}


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def _api_request(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{API_URL}/{path}"
    kwargs.setdefault("headers", {}).update(HEADERS)
    return requests.request(method, url, **kwargs)


# ----------------------------------------------------------------------
# CLI group
# ----------------------------------------------------------------------
@click.group()
def cli():
    """C2 Lab Operator CLI – manage agents and send commands."""
    pass


# ----------------------------------------------------------------------
# Command: list-agents
# ----------------------------------------------------------------------
@cli.command()
def list_agents():
    """List all registered agents with their last heartbeat."""
    resp = _api_request("GET", "agents")
    resp.raise_for_status()
    agents = resp.json()
    if not agents:
        click.echo("No agents registered.")
        return
    table = [
        [a["agent_id"], a.get("capabilities", []), a.get("last_seen", "never"), a.get("registered_at", "")]
        for a in agents
    ]
    click.echo(tabulate(table, headers=["Agent ID", "Capabilities", "Last Seen", "Registered"]))


# ----------------------------------------------------------------------
# Command: send
# ----------------------------------------------------------------------
@cli.command()
@click.argument("agent_id")
@click.argument("command_type")
@click.option("--args", default="{}", help="JSON string of arguments for the command.")
def send(agent_id: str, command_type: str, args: str):
    """Send a command to an agent."""
    import json
    try:
        parsed_args = json.loads(args)
    except json.JSONDecodeError:
        click.echo("Invalid JSON for --args", err=True)
        sys.exit(1)

    payload = {"command_type": command_type, "args": parsed_args}
    resp = _api_request("POST", f"agents/{agent_id}/command", json=payload)
    if resp.status_code == 404:
        click.echo(f"Agent {agent_id} not found.", err=True)
        sys.exit(1)
    resp.raise_for_status()
    click.echo(json.dumps(resp.json(), indent=2))


# ----------------------------------------------------------------------
# Command: watch
# ----------------------------------------------------------------------
@cli.command()
@click.argument("agent_id")
@click.option("--since", default=None, help="Filter results after this timestamp (ISO format).")
def watch(agent_id: str, since: Optional[str]):
    """Stream results from an agent."""
    resp = _api_request("GET", f"agents/{agent_id}/results")
    resp.raise_for_status()
    results = resp.json()
    for r in results:
        ts = r.get("created_at", "")
        if since and ts < since:
            continue
        click.echo(f"[{ts}] stdout: {r.get('stdout','')[:200]}")
        if r.get("stderr"):
            click.echo(f"[{ts}] stderr: {r.get('stderr')}")


# ----------------------------------------------------------------------
# Command: events
# ----------------------------------------------------------------------
@cli.command()
@click.option("--source", default="server", help="Event source identifier.")
def events(source: str):
    """Monitor events in real time via MQTT."""
    client = mqtt.Client(client_id="c2-cli")
    client.on_connect = lambda c, u, f, rc: c.subscribe("c2/logs/#")
    client.on_message = lambda c, u, m: print(f"[{m.timestamp}] {m.topic}: {m.payload.decode()}")

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    click.echo(f"Monitoring events on MQTT broker at {MQTT_HOST}:{MQTT_PORT}...")
    client.loop_forever()


if __name__ == "__main__":
    cli()