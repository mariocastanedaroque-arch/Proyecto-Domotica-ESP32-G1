# Proyecto de Domótica - Firmware ESP32 
# Funciones: Wi-Fi + MQTT + lectura de sensores + control remoto de actuadores

import network
import time
import machine
import dht
import ujson
import ubinascii
from machine import Pin, ADC, PWM
from umqtt.simple import MQTTClient

# ==========================================================
# 1. CONFIGURACIÓN DE RED Y MQTT
# ==========================================================
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = b"esp32-g1-" + ubinascii.hexlify(machine.unique_id())

# Tópicos de sensores acordados por el grupo
TOPIC_TEMPERATURA = b"casa/sala/G1temperaturaEBB115"
TOPIC_HUMEDAD = b"casa/sala/G1humedadEBB115"
TOPIC_LUZ = b"casa/sala/G1luzEBB115"  # Sin espacio: todos deben usar este mismo nombre
TOPIC_MOVIMIENTO = b"casa/entrada/G1movimientoEBB115"
TOPIC_DISTANCIA = b"casa/entrada/G1distanciaEBB115"

# Tópicos de comandos del dashboard
TOPIC_LED_CMD = b"casa/sala/G1ledEBB115/cmd"
TOPIC_VENTILADOR_CMD = b"casa/sala/G1ventiladorEBB115/cmd"
TOPIC_SERVO_CMD = b"casa/entrada/G1servoEBB115/cmd"
TOPIC_BUZZER_CMD = b"casa/entrada/G1buzzerEBB115/cmd"

# ==========================================================
# 2. CONFIGURACIÓN DE PINES (según el circuito de Luis)
# ==========================================================
# Sensores
sensor_dht = dht.DHT22(Pin(15))
ldr = ADC(Pin(34))
ldr.atten(ADC.ATTN_11DB)
pir = Pin(14, Pin.IN)
trig = Pin(5, Pin.OUT)
echo = Pin(18, Pin.IN)

# Actuadores
led_luz = Pin(23, Pin.OUT)            # LED amarillo: iluminación de sala
led_ventilador = Pin(19, Pin.OUT)     # LED azul: indicador de ventilador
servo = PWM(Pin(13), freq=50)
buzzer = PWM(Pin(27), freq=1000, duty=0)

cliente_mqtt = None

# ==========================================================
# 3. FUNCIONES DE ACTUADORES
# ==========================================================
def mover_servo(angulo):
    """Mueve el servo entre 0 y 180 grados."""
    if angulo < 0:
        angulo = 0
    elif angulo > 180:
        angulo = 180

    # En ESP32 con MicroPython: duty va de 0 a 1023.
    duty = int(25 + (angulo / 180) * 100)
    servo.duty(duty)


def controlar_buzzer(activar):
    """Activa o apaga el buzzer de alarma."""
    buzzer.duty(512 if activar else 0)


# ==========================================================
# 4. FUNCIONES DE SENSORES
# ==========================================================
def medir_distancia():
    """Devuelve la distancia del HC-SR04 en centímetros."""
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    duracion = machine.time_pulse_us(echo, 1, 30000)
    if duracion < 0:
        return None

    return round((duracion * 0.0343) / 2, 2)


def leer_dht22():
    """Lee temperatura y humedad, sin detener el programa si falla una lectura."""
    try:
        sensor_dht.measure()
        return sensor_dht.temperature(), sensor_dht.humidity()
    except OSError:
        print("Advertencia: no se pudo leer el DHT22 en este ciclo")
        return None, None


# ==========================================================
# 5. WIFI Y MQTT
# ==========================================================
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Conectando a Wi-Fi", end="")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        while not wlan.isconnected():
            print(".", end="")
            time.sleep(0.5)

    print("\nWi-Fi conectado correctamente")
    print("IP asignada:", wlan.ifconfig()[0])
    return wlan


def interpretar_estado(mensaje):
    """Acepta el JSON acordado: {\"estado\": \"ON\"} o {\"estado\": \"OFF\"}."""
    try:
        datos = ujson.loads(mensaje.decode())
        estado = str(datos.get("estado", "")).upper()
        return estado, datos
    except Exception:
        # Permite pruebas simples con ON u OFF, aunque el proyecto usará JSON.
        return mensaje.decode().strip().upper(), {}


def al_recibir_comando(topic, msg):
    """Se ejecuta automáticamente cuando llega un comando desde MQTT."""
    topic_str = topic.decode()
    estado, datos = interpretar_estado(msg)

    print("Comando recibido en", topic_str, ":", msg.decode())

    if topic == TOPIC_LED_CMD:
        led_luz.value(1 if estado == "ON" else 0)
        print("LED de sala:", "ENCENDIDO" if estado == "ON" else "APAGADO")

    elif topic == TOPIC_VENTILADOR_CMD:
        led_ventilador.value(1 if estado == "ON" else 0)
        print("Ventilador:", "ENCENDIDO" if estado == "ON" else "APAGADO")

    elif topic == TOPIC_SERVO_CMD:
        # ON abre la puerta a 90°, OFF la cierra a 0°.
        # También acepta {"angulo": 45} si se quiere controlar una apertura parcial.
        if "angulo" in datos:
            angulo = int(datos["angulo"])
        else:
            angulo = 90 if estado == "ON" else 0

        mover_servo(angulo)
        print("Puerta/servo movido a", angulo, "grados")

    elif topic == TOPIC_BUZZER_CMD:
        controlar_buzzer(estado == "ON")
        print("Buzzer:", "ACTIVADO" if estado == "ON" else "APAGADO")


def conectar_mqtt():
    """Conecta el ESP32 al broker y se suscribe a los cuatro comandos."""
    global cliente_mqtt

    print("Conectando al broker MQTT...", end="")
    cliente_mqtt = MQTTClient(
        MQTT_CLIENT_ID,
        MQTT_BROKER,
        port=MQTT_PORT,
        keepalive=60
    )
    cliente_mqtt.set_callback(al_recibir_comando)
    cliente_mqtt.connect()

    cliente_mqtt.subscribe(TOPIC_LED_CMD)
    cliente_mqtt.subscribe(TOPIC_VENTILADOR_CMD)
    cliente_mqtt.subscribe(TOPIC_SERVO_CMD)
    cliente_mqtt.subscribe(TOPIC_BUZZER_CMD)

    print(" conectado")
    print("Suscrito a los 4 tópicos de comandos")


def publicar_lectura(topic, valor, unidad):
    """Publica una lectura siguiendo el JSON acordado por el grupo."""
    if valor is None:
        return

    payload = {
        "valor": valor,
        "unidad": unidad,
        "ts": time.time()
    }
    mensaje = ujson.dumps(payload)
    cliente_mqtt.publish(topic, mensaje)
    print("Publicado en {}: {}".format(topic.decode(), mensaje))


# ==========================================================
# 6. PROGRAMA PRINCIPAL
# ==========================================================
def main():
    global cliente_mqtt

    print("Iniciando Sistema de Casa Inteligente - Grupo 1")

    # Estado inicial seguro de los actuadores.
    led_luz.value(0)
    led_ventilador.value(0)
    controlar_buzzer(False)
    mover_servo(0)

    conectar_wifi()
    conectar_mqtt()

    # Publicar valores de sensores cada 2 segundos.
    ultimo_reporte = time.ticks_ms()
    INTERVALO_REPORTE = 2000

    while True:
        try:
            # Escucha comandos sin bloquear la lectura de los sensores.
            cliente_mqtt.check_msg()

            ahora = time.ticks_ms()
            if time.ticks_diff(ahora, ultimo_reporte) >= INTERVALO_REPORTE:
                temperatura, humedad = leer_dht22()
                luz_adc = ldr.read()
                luz_porcentaje = round((luz_adc * 100) / 4095, 2)
                movimiento = pir.value()
                distancia = medir_distancia()

                # Un mensaje MQTT por cada sensor, usando los tópicos definidos.
                publicar_lectura(TOPIC_TEMPERATURA, temperatura, "C")
                publicar_lectura(TOPIC_HUMEDAD, humedad, "%")
                publicar_lectura(TOPIC_LUZ, luz_porcentaje, "%")
                publicar_lectura(TOPIC_MOVIMIENTO, movimiento, "estado")
                publicar_lectura(TOPIC_DISTANCIA, distancia, "cm")

                print("--- Ciclo de sensores completado ---")
                ultimo_reporte = ahora

            time.sleep_ms(100)

        except OSError as error:
            # Si el broker público se desconecta, intenta reconectar sin detener la simulación.
            print("Error de red/MQTT:", error)
            time.sleep(2)
            try:
                conectar_mqtt()
            except Exception as error_reconexion:
                print("No se pudo reconectar todavía:", error_reconexion)
                time.sleep(3)

        except Exception as error:
            print("Error inesperado:", error)
            time.sleep(1)


main()
