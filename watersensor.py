#!/usr/bin/python3
import time
import asyncio
import os
from datetime import datetime
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
lastpush = datetime.now()
shutdown = False

def gpiosetup():
    GPIO.setmode(GPIO.BCM)
    gpio_in_low = (17,27,22,13,19,26,18,23,24,25,12,16,20,21)
    for gpio in gpio_in_low:
        GPIO.setup(gpio, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    gpio_in_high = (4,5)
    for gpio in gpio_in_high:
        GPIO.setup(gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(6, GPIO.OUT)
    GPIO.output(6, 0)
    def gpioupcb5(pin):
        global menucounter
        global lastpush
        lastpush = datetime.now()
        menucounter = (menucounter + 1) % 3
        #print("PIN5 Counter", menucounter )
    GPIO.add_event_detect(5, GPIO.BOTH,  callback=gpioupcb5, bouncetime=300)  



async def shutdown_detect():
    global lastpush
    global shutdown
    while True:
        diff = (datetime.now() - lastpush).total_seconds()
        if not GPIO.input(5) and diff > 1:
            print("Shutdown begin in 3 seconds!",datetime.now())
            for i in (3,2,1):
                await asyncio.sleep(1)
                diff = (datetime.now() - lastpush).total_seconds()
                if GPIO.input(5):
                    print("Shutdown CANCELLED!")
                    break
                if diff > 4:
                    shutdown = True
                    print("SHUTDOWN STARTING!")
                    await asyncio.sleep(1)
                    os.system("shutdown now");
                    exit();
        else:
            #print("No Shutdown detected...",datetime.now())
            await asyncio.sleep(1)


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
        await asyncio.sleep(0.5)
        water = (ch2*100)/ch3
        thresh = (ch1*100)/ch3
        #print(menucounter)
        if shutdown:
            oled("SHUTDOWN\n"+str(datetime.now()), font16)
            break
        if menucounter == 0 and ch0 !=None and ch2 != None:
            pct = 'Water Level\n{0:0.2f} %'.format(water)
            oled(pct, font16)
        if menucounter == 1 and ch0 !=None and ch1 !=None:
            pct = 'Threshold\n{0:0.2f} %'.format(thresh)
            oled(pct, font16)
        if menucounter == 2:
            oled('{0:0.4f} V\n'.format(ch0) + '{0:0.4f} V\n'.format(ch1) +'{0:0.4f} V\n'.format(ch2) +'{0:0.4f} V'.format(ch3), font)
        #oled(temp_humi,font16)
        await asyncio.sleep(0.5)

async def console():
    global ch0
    global ch1
    global ch2
    global ch3
    print("Start Console")
    while True:
        #print ( time.strftime('%H:%M:%S'),pct,temp1,temp2,humi,"{:7.4f} V".format(ch0), "{:7.4f} V".format(ch1), "{:7.4f} V".format(ch2), "{:7.4f} V".format(ch3), )
        if ch0 == None or ch1 == None or ch2 == None or ch3 == None:
            print("No values yet")
        else:
            print ( time.strftime('%H:%M:%S'),"{:7.4f} V".format(ch0), "{:7.4f} V".format(ch1), "{:7.4f} V".format(ch2), "{:7.4f} V".format(ch3) )
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
            if ch2 > ch1:
                GPIO.output(6,1)
            else:
                GPIO.output(6,0)
#            else:
#	        GPIO.output(6,1)
        except Exception as e:
            print(datetime.now(),"ADS1115 READ ERROR:",e)
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
                pct = (ch2/ch0)*100
                ws.send(str(pct))
                result =  ws.recv()
        except Exception as e:
            print("websocket send failed",e)
        await asyncio.sleep(5)


try:
	print('Reading ADS1x15 AND HTU21D values, press Ctrl-C to quit...')
	gpiosetup()
	loop = asyncio.get_event_loop()
	#loop.run_until_complete(asyncio.gather( shutdown_detect(), wssend(),console(),display(),sensor_ad()))
	loop.run_until_complete(asyncio.gather( sensor_ad(), shutdown_detect(),  display(), console(), wssend()  ))
	loop.close()
except KeyboardInterrupt:
	print("Keyboard Interrupt")
except Exception as e:
	print("Other error",e)
finally:
	GPIO.cleanup()

