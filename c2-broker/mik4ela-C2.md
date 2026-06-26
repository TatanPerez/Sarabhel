# Transporte y Criptografia — Sarabhel C2

Este documento se fusionó en el README principal para tener una sola fuente de verdad.

➡️ **Ver [`README.md`](./README.md)**

Contiene:

- Arquitectura y diseño del sistema
- Contrato de comunicación (tópicos sincronizados)
- Integración de agentes (Python)
- Integración con n8n (bridge HTTP)
- Gestión de certificados
- Políticas de acceso (ACL)
- Checklist y troubleshooting

Los principios de diseño se mantienen:

- **AES-256-GCM** con nonce contador persistente
- **QoS 1** para agents dormidos
- **Tópicos opacos** con IDs únicos y estructura plana
