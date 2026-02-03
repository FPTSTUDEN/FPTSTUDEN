from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os
# print("Testing script running...")
WeekAndMonth = {"Sunday":"星期日","Monday":"星期一","Tuesday":"星期二","Wednesday":"星期三","Thursday":"星期四","Friday":"星期五","Saturday":"星期六","January":"一月","February":"二月","March":"三月","April":"四月","May":"五月","June":"六月","July":"七月","August":"八月","September":"九月","October":"十月","November":"十一月","December":"十二月"}
# Date={"0":"零","1":"一","2":"二","3":"三","4":"四","5":"五","6":"六","7":"七","8":"八","9":"九"}
Date={"01":"The first","02":"Second","03":"Third","04":"Fourth","05":"Fifth","06":"Sixth","07":"Seventh","08":"Eighth","09":"Ninth","10":"Tenth","11":"Eleventh","12":"Twelfth","13":"Thirteenth","14":"Fourteenth","15":"Fifteenth","16":"Sixteenth","17":"Seventeenth","18":"Eighteenth","19":"Nineteenth","20":"Twentieth","21":"Twenty first","22":"Twenty2nd","23":"Twenty3rd","24":"Twenty4th","25":"Twenty5th","26":"Twenty6th","27":"Twenty7th","28":"Twenty8th","29":"Twenty9th","30":"Thirtieth","31":"Thirty first"}
# Date={"01":"The first","02":"Second","03":"Third","04":"Fourth","05":"Fifth","06":"Sixth","07":"Seventh","08":"Eighth","09":"Ninth","10":"Tenth","11":"Eleventh","12":"Twelfth","13":"Thirteenth","14":"Fourteenth","15":"Fifteenth","16":"Sixteenth","17":"Seventeenth","18":"Eighteenth","19":"Nineteenth","20":"Twentieth","21":"Twenty first","22":"Twenty second","23":"Twenty third","24":"Twenty fourth","25":"Twenty fifth","26":"Twenty sixth","27":"Twenty seventh","28":"Twenty eight","29":"Twenty ninth","30":"Thirtieth","31":"Thirty first"}

Month={"0":"零","1":"一","2":"二","3":"三","4":"四","5":"五","6":"六","7":"七","8":"八","9":"九","10":"十","11":"十一","12":"十二"}
color1=(200,200,200)
color2=(188, 188, 85)
# Get current date
now = datetime.utcnow()
day,month,year=now.day, now.month, now.year
weekday=now.strftime("%A")
date_str = now.strftime("%Y-%m-%d")
time_str = now.strftime("%H:%M:%S UTC")
# Create image with transparent background
width, height = 400, 400
image = Image.new('RGBA', (width, height), color=(0,0,0,0))
draw = ImageDraw.Draw(image)

try:
    scale=1.5
    # Try to use a nice font if available
    # ./Mengshen-Handwritten.ttf
    font_extra_large = ImageFont.truetype("guyin.ttf", int(120*scale))
    font_date= ImageFont.truetype("Brownhill-Script.ttf", int(60*scale))
    font_weekday = ImageFont.truetype("HanWangWCL03.ttf", int(35*scale))
    font_month_year= ImageFont.truetype("shizizuoziti.ttf", int(40*scale))
    font_large = ImageFont.truetype("Mengshen-Handwritten.ttf", int(40*scale))
    font_small = ImageFont.truetype("Mengshen-Handwritten.ttf", int(20*scale))
except:
    # Fallback to default font
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()
# Upper left large weekday in Chinese
draw.text((20, 20), WeekAndMonth[weekday][2],
          fill=(220, 220, 220), font=font_extra_large)
# Day in English (lower left,vertical - 90 degrees to left)
day_str=""+Date[f"{day:02d}"]+"" #if day>=13 and day<=19 else Date[f"{day:02d}"]
day_image=Image.new('RGBA', (300, 200), color=(0,0,0,0))
day_draw=ImageDraw.Draw(day_image)
day_draw.text((20, 0), day_str,
    fill=color2, font=font_date)
# Rotate and paste the day image onto main image
day_image = day_image.rotate(90, expand=True)
image.paste(day_image, (int(width/5), 50),day_image)
# Month
draw.text((width - 60, int(height/1.85)), "&"+Month[f"{month}"]+"月",
          fill=color1, font=font_month_year, anchor="rm")
# Year
# print(year)
draw.text((width - 95, int(height/1.47)), str(year),
          fill=color1, font=font_month_year, anchor="rm")

# Draw week day (center right)
draw.text((width - 50 , int(height/2.5)), WeekAndMonth[weekday],
          fill=color2, font=font_weekday, anchor="rm")
# image.show()
# Save image
os.makedirs('public', exist_ok=True)
os.chdir('public')
image.save('date-image.png', 'PNG')

print(f"Generated date image: {date_str}")

