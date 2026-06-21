# Proyecto de Domótica con ESP32

Proyecto de Sistemas Embebidos desarrollado en Wokwi.

## Integrantes
- Luis: Hardware y simulación en Wokwi.
- Mario Josué Castañeda Roque: Firmware del ESP32, Wi-Fi y MQTT.
- Oswaldo: Broker MQTT, gateway y base de datos.
- Kevin: Dashboard.
- Jacqueline: Arquitectura, integración, documento y video.

## Enlace de simulación Wokwi
https://wokwi.com/projects/467462230230836225

## Funcionalidades
- Lectura de temperatura y humedad mediante DHT22.
- Lectura de luz mediante LDR.
- Detección de movimiento con PIR.
- Medición de distancia mediante HC-SR04.
- Control remoto de iluminación, ventilador, servo y buzzer.
- Comunicación mediante Wi-Fi y MQTT.

## Broker MQTT
- Broker: broker.hivemq.com
- Puerto ESP32: 1883

## Tópicos de sensores
- casa/sala/G1temperaturaEBB115
- casa/sala/G1humedadEBB115
- casa/sala/G1luzEBB115
- casa/entrada/G1movimientoEBB115
- casa/entrada/G1distanciaEBB115

## Tópicos de comandos
- casa/sala/G1ledEBB115/cmd
- casa/sala/G1ventiladorEBB115/cmd
- casa/entrada/G1servoEBB115/cmd
- casa/entrada/G1buzzerEBB115/cmd

## Formato de comando
```json
{"estado":"ON"}
