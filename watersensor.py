import time
import asyncio
from websocket import create_connection
import Adafruit_ADS1x15
import Adafruit_HTU21D.HTU21D as HTU21D
import RPi.GPIO as GPIO
import Adafruit_SSD1306
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

menucounter = 0
tempf = None
tempc = None
humi = None
ch0 = None
ch1 = None
ch2 = None
ch3 = None

def gpiosetup():
    GPIO.setmode(GPIO.BCM)
    #GPIO.cleanup()
    gpio_in_low = (4,17,27,22,13,19,26,  18,23,24,25,12,16,20,21)
    for gpio in gpio_in_low: GPIO.setup(gpio, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    gpio_in_high = (5,6)
    for gpio in gpio_in_high: GPIO.setup(gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    def gpiocb5(pin):
            global menucounter
            menucounter = (menucounter + 1) % 6
            #print("PIN5 Counter", menucounter )
    GPIO.add_event_detect(5, GPIO.BOTH, callback=gpiocb5, bouncetime=300)  



async def display():
    global menucounter
    print("Start Display")
    disp = Adafruit_SSD1306.SSD1306_128_32(rst=None)
    disp.begin()
    disp.clear()
    font = ImageFont.load_default()
    font8 = ImageFont.truetype('Minecraftia.ttf', 8)
    font16 = ImageFont.truetype('Minecraftia.ttf', 16)
    font32 = ImageFont.truetype('Minecraftia.ttf', 32)
    image = Image.new('1', (disp.width, disp.height))
    draw = ImageDraw.Draw(image)

    def oled(text,font):
        draw.rectangle((0,0,disp.width,disp.height), outline=0, fill=0)
        lines = text.splitlines()
        lineNumber = 0
        size = 8
        top = -2
        if font == font16: size = 16
        if font == font32: size = 32
        for line in lines:
            draw.text((0, top+lineNumber*size), line, font=font, fill=255)
            lineNumber += 1
        disp.image(image)
        disp.display()
    
    while True:
        if menucounter == 0 and ch0 !=None and ch1 !=None:
            pct = 'Water Level\n{0:0.2f} %'.format((ch0*100)/ch1)
            oled(pct, font16)
        if menucounter == 1 and tempc !=None and tempf !=None and humi !=None:
            temp_humi = "Temp: "+'{0:0.1f}F'.format(tempf)+"\nHumid: "+'{0:0.1f}%'.format(humi)
            oled(temp_humi, font16)
        if menucounter == 2:
            oled("CH0 Voltage:\n"+'{0:0.4f} V'.format(ch0), font16)
        if menucounter == 3:
            oled("CH1 Voltage:\n"+'{0:0.4f} V'.format(ch1), font16)
        if menucounter == 4:
            oled("CH2 Voltage:\n"+'{0:0.4f} V'.format(ch2), font16)
        if menucounter == 5:
            oled("CH3 Voltage:\n"+'{0:0.4f} V'.format(ch3), font16)
        #oled(temp_humi,font16)
        await asyncio.sleep(0.5)
        
async def console():
    print("Start Display")
    while True:
        #print ( time.strftime('%H:%M:%S'),pct,temp1,temp2,humi,"{:7.4f} V".format(ch0), "{:7.4f} V".format(ch1), "{:7.4f} V".format(ch2), "{:7.4f} V".format(ch3), )
        await asyncio.sleep(1)


async def sensor_ad():
    global ch0
    global ch1
    global ch2
    global ch3
    print("Start A/D Sensor")
    adc = Adafruit_ADS1x15.ADS1115()
    GAIN = 1
    VMULTI = (0.125/GAIN)/1000
    while True:
        try:
            ch0 = adc.read_adc(0, gain=GAIN) * VMULTI
            ch1 = adc.read_adc(1, gain=GAIN) * VMULTI
            ch2 = adc.read_adc(2, gain=GAIN) * VMULTI
            ch3 = adc.read_adc(3, gain=GAIN) * VMULTI
            #print("A/D Success")
        except Exception as e:
            print("Analog Digital Sensor read error",e)
        await asyncio.sleep(1)

async def sensor_temp():
    global tempc
    global tempf
    global humi
    print("Start Temperature Sensor")
    sensor = HTU21D.HTU21D()
    while True:
        try:
            tempc = sensor.read_temperature()
            tempf = tempc*(9/5)+32
            #temp1 = '{0:0.2f} C'.format(tempc)
            #temp2 = '{0:0.2f} F'.format(tempf)
            humi = sensor.read_humidity()
            #print("Temperature Success!")
        except Exception as e:
            print("Temperature Sensor read error",e)
        await asyncio.sleep(2)

# library is websocket-client
async def wssend():
    global pct
    try:
        ws = create_connection("ws://127.0.0.1:8080/ws")
    except Exception as e:
        print("websocket open failed",e)
    while True:
        try:
            if ch0 == None or ch1 == None:
                print("Nothing to send")
            else:
                pct = (ch0/ch1)*100
                ws.send(str(pct))
                result =  ws.recv()
        except Exception as e:
            print("websocket send failed",e)
        await asyncio.sleep(5)

print('Reading ADS1x15 AND HTU21D values, press Ctrl-C to quit...')
gpiosetup()
loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(wssend(),console(),display(),sensor_ad(),sensor_temp()))
loop.close()
