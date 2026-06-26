# Transporte y Criptografia

Se diseña un canal C2 con MQTT, donde se utiliza contenedores docker para aislar el Broker. El Broker actuara como un proxy asincrono y tendra en cuenta los siguientes puntos:

- Se elige AES en modo GCM, ya que proporciona cifrado y auth simultaneamente. Se genera un Nonce Script criptograficamente seguro y aleatorio para cada mensaje enviado.

- Calidad de servicio QoS, para no perder mensajes si el agente esta dormido. Se configura el Pub y en Sub con QoS1 o QoS2 para retener el mensaje mientras el agente despierta.

- Topicos Opacos, tendran identificadores unicos y una estructura plana.
