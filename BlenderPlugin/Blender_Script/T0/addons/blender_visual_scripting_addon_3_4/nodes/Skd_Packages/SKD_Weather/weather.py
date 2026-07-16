import bpy
import requests
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_weatherNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_weatherNode"
    bl_label = "Weather"
    bl_width_default = 300
    node_color = (0.207644, 0.431545, 0.593935)
    bl_icon = "OUTLINER_OB_VOLUME"

    Weather_location: bpy.props.StringProperty(name="Weather Location",
                                    description="Location")
    Weather_temp: bpy.props.StringProperty(name="Weather Temp",
                                    description="Location")
    Weather_wind: bpy.props.StringProperty(name="Weather Wind",
                                    description="Location")
    Weather_Humidity: bpy.props.StringProperty(name="Weather Humidity",
                                    description="Location")
    Weather_Cloudiness: bpy.props.StringProperty(name="Weather Clouds",
                                    description="Location")
    Weather_description: bpy.props.StringProperty(name="Weather Description",
                                    description="Location")
    
    
    ####
    show_box: bpy.props.BoolProperty(
        name="Show Box",
        description="Show or hide the box layout",
        default=False
    )
    ####


    def on_create(self, context):
        self.add_string_input("api").default_value = ""
        self.add_string_input("lat").default_value = ""
        self.add_string_input("lon").default_value = ""

    def get_weather(self, api_key, lat, lon):
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
        response = requests.get(url)
        data = response.json()
        return data

    def _evaluate(self, context):
        # Check if all input sockets are available
        if len(self.inputs) < 3:
            return
        

        weather_colours = {
            "clear sky": (0.232011, 0.508016, 0.479424),
            "thunderstorm with light rain": (0, 0, 0.50196),  # Dark Blue
            "thunderstorm with rain": (0, 0, 1),  # Blue
            "thunderstorm with heavy rain": (0, 0, 0.5451),  # Dark Blue
            "thunderstorm with light drizzle": (0.2549, 0.41176, 0.88235),  # Royal Blue
            "thunderstorm with drizzle": (0.28235, 0.23922, 0.5451),  # Dark Slate Blue
            "thunderstorm with heavy drizzle": (0, 0, 0.50196),  # Navy
            "light rain": (0.6902, 0.7686, 0.8706),  # Light Steel Blue
            "moderate rain": (0.2745, 0.5098, 0.7059),  # Steel Blue
            "heavy intensity rain": (0.098, 0.098, 0.4392),  # Midnight Blue
            "very heavy rain": (0, 0, 0.50196),  # Navy
            "extreme rain": (0, 0, 0.5451),  # Dark Blue
            "freezing rain": (0.5294, 0.8078, 0.9804),  # Light Sky Blue
            "light intensity shower rain": (0, 0.5647, 1),  # Dodger Blue
            "shower rain": (0, 0, 1),  # Blue
            "heavy intensity shower rain": (0, 0, 0.5451),  # Dark Blue
            "ragged shower rain": (0, 0, 0.50196),  # Navy
            "light snow": (1, 0.9804, 0.9804),  # Snow
            "snow": (1, 0.9804, 0.9804),  # Snow
            "heavy snow": (1, 0.9804, 0.9804),  # Snow
            "sleet": (0.9412, 1, 1),  # Azure
            "light shower sleet": (0.8784, 1, 1),  # Light Cyan
            "shower sleet": (0.8784, 1, 1),  # Light Cyan
            "light rain and snow": (0.9412, 1, 1),  # Azure
            "rain and snow": (0.9412, 1, 1),  # Azure
            "Light shower snow": (0.9412, 1, 1),  # Azure
            "shower snow": (0.9412, 1, 1),  # Azure
            "heavy shower snow": (0.9412, 1, 1),  # Azure
            "clear": (0.232011, 0.508016, 0.479424),  # Different Color
            "few clouds": (0.626612, 0.631141, 0.684487),  # Different Color
            "scattered clouds": (0.568159, 0.637673, 0.684487),  # Different Color
            "broken clouds": (0.406586, 0.495006, 0.508016),  # Different Color
            "shower rain": (0.057004, 0.026611, 0.096251),  # Different Color
            "rain": (0.088113, 0.093751, 0.096251),  # Different Color
            "light rain": (0.088113, 0.093751, 0.096251),  # Different Color
            "thunderstorm": (0.550797, 0.550797, 0.491156),  # Different Color
            "snow": (0.679139, 0.649727, 0.646252),  # Different Color
            "mist": (0.679139, 0.533161, 0.414394),  # Different Color
            "heavy intensity rain": (0.175639, 0.169883, 0.18716),  # Different Color
            "overcast clouds": (0.146015, 0.18429, 0.18716)
        }

        api_s = self.inputs[0].default_value
        lat_s = self.inputs[1].default_value
        lon_s = self.inputs[2].default_value
            
        weather_data = self.get_weather(api_s, lat_s, lon_s)

        if "main" in weather_data:
            self.Weather_location = str(weather_data['name'])
            temperature_celsius = int(weather_data['main']['temp'] - 273.15)
            self.Weather_temp = str(temperature_celsius) + " °C"
            self.Weather_wind = str(weather_data['wind']['speed']) + " mph"
            self.Weather_Humidity = str(weather_data['main']['humidity']) + " %"
            self.Weather_Cloudiness = str(weather_data['clouds']['all']) + " %"
            self.Weather_description = str(weather_data["weather"][0]["description"])

            # Check if the weather description is in the predefined colors
            if self.Weather_description in weather_colours:
                self.color = weather_colours[self.Weather_description]


    def draw_node(self, context, layout):
        #########
        """
        Click the open weather website button
        Obtain an API and add this to your node
        Set Lat and Lon to be the region you want
        The node should change colour based on the weather settings for that location
        """
        # Extract the docstring dynamically from the current method
        docstring = self.__class__.draw_node.__doc__
        display_text = docstring.strip() if docstring else "No info available"

        row_skd = layout.row()
        if self.show_box:
            row_skd.prop(self, "show_box", icon="TRIA_DOWN", text="Hide Info", emboss=False)
        else:
            row_skd.prop(self, "show_box", icon="TRIA_RIGHT", text="Show Info", emboss=False)

        if self.show_box:
            box_skd = layout.box()

            # Split docstring into multiple lines and add each line as a label
            for line in display_text.split("\n"):
                box_skd.label(text=line.strip())
        #########

        row = layout.row()
        col1 = row.column()
        # Add a button to open the website
        col1.operator("wm.url_open", text="Open Weather Website").url = "https://openweathermap.org/"
        col1.label(text="Location: " + self.Weather_location)
        col1.label(text="Temperature: " + self.Weather_temp)
        col1.label(text="Wind: " + self.Weather_wind)
        col1.label(text="Humidity: " + self.Weather_Humidity)
        col1.label(text="Cloudiness: " + self.Weather_Cloudiness)
        col1.label(text="Description: " + self.Weather_description)