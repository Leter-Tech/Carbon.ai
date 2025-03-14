from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
from datetime import datetime
import base64
import tempfile
import json
import re

app = Flask(__name__)

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    api_key = "REMOVED"

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

PROMPTS = {
    'purchase': """Analyze this receipt image and provide the following information in JSON format:
        1. Total carbon footprint in KG CO2 (mandatory to give a number approx.)
        2. Category should be "Purchase"
        3. Description of the items and purchases
        4. AI tips for reducing carbon footprint on purchases
        5. Do not give null or zero values in carbon footprint, just give approximate values
        6. Calculate the carbon footprint on upper limit which means give higher end values of carbon footprint not the mean values
        7. Give tips and description in line format, do not give in list format and do not use bold or italic text

        Format:
        {
            "carbon_footprint": number,
            "category": "Purchase",
            "description": string,
            "recommendations": string
        }
    """,
    
    'food': """Analyze this food image and provide the following information in JSON format:
        1. Total carbon footprint in KG CO2 (mandatory to give a float number approx.)
        2. Category should be "Food"
        3. Description of the food items
        4. AI tips for reducing food-related carbon footprint
        5. Give upper limit values of carbon footprint not the mean values
        6. Give tips and description in line format, do not give in list format and do not use bold or italic text

        Format:
        {
            "carbon_footprint": float number,
            "category": "Food",
            "description": string,
            "recommendations": string
        }
    """,
    
    'waste': """Analyze this waste image and provide the following information in JSON format:
        1. Total carbon footprint in KG CO2 (mandatory to give a number approx.)
        2. Category should be "Waste"
        3. Description of the waste items
        4. AI tips for better waste management
        5. Give upper limit values of carbon footprint not the mean values
        6. Give tips and description in line format, do not give in list format and do not use bold or italic text
        Format:
        {
            "carbon_footprint": float number,
            "category": "Waste",
            "description": string,
            "recommendations": string
        }
    """,
    
    'offset': """Analyze this environmental activity image and provide the following information in JSON format:
        1. Carbon offset in KG CO2 (mandatory to give a float number approx., should be negative)
        2. Category should be "Offset"
        3. Description of the environmental activity
        4. AI tips for maximizing impact
        5. Give tips and description in line format, do not give in list format and do not use bold or italic text

        Format:
        {
            "carbon_footprint": negative float number,
            "category": "Offset",
            "description": string,
            "recommendations": string
        }
    """
}

def clean_and_parse_response(response_text):
    try:
        cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
        print(cleaned_text)
        json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
        if not json_match:
            print("No JSON found in response:", cleaned_text)  
            raise ValueError("Invalid response format from AI")
        
        json_str = json_match.group(0)
        
        json_str = re.sub(r'[\n\r\t]', '', json_str)
        json_str = re.sub(r',\s*}', '}', json_str)  
        json_str = re.sub(r'\s+', ' ', json_str)    
        
        data = json.loads(json_str)
        
        required_fields = ['carbon_footprint', 'category', 'description', 'recommendations']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        try:
            data['carbon_footprint'] = round(float(str(data['carbon_footprint']).strip()), 3)
        except (ValueError, TypeError):
            raise ValueError("Invalid carbon_footprint value")
        
        return data

    except json.JSONDecodeError as e:
        print("JSON Decode Error:", str(e))  
        print("Attempted to parse:", json_str)  
        raise ValueError("Invalid JSON format in response")
    except Exception as e:
        print("Unexpected error in parse_response:", str(e))  
        raise ValueError(f"Error processing AI response: {str(e)}")

@app.route('/')
def home():
    return render_template('carbon_ai.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')

@app.route('/legal')
def legal():
    return render_template('legal.html')

@app.route('/account')
def account():
    return render_template('account.html')

@app.route('/process_image', methods=['POST'])
def process_image():
    try:
        category = request.json.get('category')
        image_data = request.json.get('image')
        image_data = image_data.split(',')[1]

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(base64.b64decode(image_data))
            temp_path = temp_file.name

        image_file = genai.upload_file(path=temp_path)
        response = model.generate_content([image_file, PROMPTS[category]])
        
        os.unlink(temp_path)

        if not response.text:
            raise ValueError("Empty response from AI")

        result = clean_and_parse_response(response.text)
        result['date'] = datetime.now().strftime('%Y-%m-%d')
        
        return jsonify(result)

    except Exception as e:
        print(f"Error processing image: {str(e)}")  
        return jsonify({'error': str(e)}), 500

@app.route('/process_text', methods=['POST'])
def process_text():
    try:
        category = request.json.get('category')
        data = request.json.get('data')
        
        if not category or not data:
            return jsonify({'error': 'Missing category or data'}), 400

        
        if category == 'energy':
            prompt = f"""
            
            Based on the following table, calculate the carbon footprint for the given electrical appliance usage
            
            - Air Conditioner (Window Unit): 1.2–2.0 kWh per hour (0.6–1.0 kg CO₂ per hour)
            - Air Purifier: 0.03–0.1 kWh per hour (0.015–0.05 kg CO₂ per hour)
            - Blender: 0.3 kWh per hour (0.15 kg CO₂ per hour)
            - Coffee Maker (Standard): 0.08–0.1 kWh per hour (0.04–0.05 kg CO₂ per hour)
            - Clothes Dryer (Electric): 2.0–4.0 kWh per hour (1.0–2.0 kg CO₂ per hour)
            - Clothes Washer (Front Load): 0.3–2.0 kWh per hour (0.15–1.0 kg CO₂ per hour)
            - Dishwasher: 1.5–2.0 kWh per hour (0.75–1.0 kg CO₂ per hour)
            - Electric Fan: 0.05–0.1 kWh per hour (0.025–0.05 kg CO₂ per hour)
            - Electric Heater (Space Heater): 1.5–2.0 kWh per hour (0.75–1.0 kg CO₂ per hour)
            - Electric Kettle: 1.5–2.5 kWh per hour (0.75–1.25 kg CO₂ per hour)
            - Electric Oven: 2.0–3.5 kWh per hour (1.0–1.75 kg CO₂ per hour)
            - Electric Stove (Single Burner): 1.0–2.0 kWh per hour (0.5–1.0 kg CO₂ per hour)
            - Electric Toothbrush: 0.005–0.02 kWh per hour (0.0025–0.01 kg CO₂ per hour)
            - Freezer (Chest or Upright): 0.2–0.6 kWh per hour (0.1–0.3 kg CO₂ per hour)
            - Hair Dryer: 0.8–1.5 kWh per hour (0.4–0.75 kg CO₂ per hour)
            - Humidifier: 0.05–0.1 kWh per hour (0.025–0.05 kg CO₂ per hour)
            - Iron: 1.0–1.2 kWh per hour (0.5–0.6 kg CO₂ per hour)
            - Microwave: 0.6–1.2 kWh per hour (0.3–0.6 kg CO₂ per hour)
            - Mixer/Grinder: 0.3–0.5 kWh per hour (0.15–0.25 kg CO₂ per hour)
            - Refrigerator (Standard Size): 0.1–0.2 kWh per hour (0.05–0.1 kg CO₂ per hour)
            - Rice Cooker: 0.5–1.0 kWh per hour (0.25–0.5 kg CO₂ per hour)
            - Router (Wi-Fi): 0.005–0.02 kWh per hour (0.0025–0.01 kg CO₂ per hour)
            - Vacuum Cleaner: 0.5–1.0 kWh per hour (0.25–0.5 kg CO₂ per hour)
            - Water Heater (Electric): 3.0–4.0 kWh per hour (1.5–2.0 kg CO₂ per hour)
            - Television (LED): 0.08–0.2 kWh per hour (0.04–0.1 kg CO₂ per hour)
            - Television (Plasma): 0.2–0.4 kWh per hour (0.1–0.2 kg CO₂ per hour)
            - Toaster: 0.6–1.0 kWh per hour (0.3–0.5 kg CO₂ per hour)
            - Toaster Oven: 1.0–1.5 kWh per hour (0.5–0.75 kg CO₂ per hour)
            - Washing Machine (Top Load): 0.3–2.0 kWh per hour (0.15–1.0 kg CO₂ per hour)
            - Water Pump: 1.0–2.0 kWh per hour (0.5–1.0 kg CO₂ per hour)
            - Xbox / PlayStation (Gaming Console): 0.1–0.2 kWh per hour (0.05–0.1 kg CO₂ per hour)
            - Desktop Computer: 0.3–0.5 kWh per hour (0.15–0.25 kg CO₂ per hour)
            - Laptop: 0.05–0.1 kWh per hour (0.025–0.05 kg CO₂ per hour)
            - Electric Fireplace: 1.0–1.5 kWh per hour (0.5–0.75 kg CO₂ per hour)
            - Smart Speakers (e.g., Amazon Echo, Google Home): 0.003–0.01 kWh per hour (0.0015–0.005 kg CO₂ per hour)
            - Electric Grill: 1.0–1.5 kWh per hour (0.5–0.75 kg CO₂ per hour)
            - Gaming PC: 0.4–1.0 kWh per hour (0.2–0.5 kg CO₂ per hour)
            - Home Theater System: 0.1–0.3 kWh per hour (0.05–0.15 kg CO₂ per hour)
            - Electric Pressure Cooker (Instant Pot): 0.6–1.0 kWh per hour (0.3–0.5 kg CO₂ per hour)

            Please analyze this transport usage and provide a JSON response, use the above table for calculation:
            Appliance: {data['appliance']}
            Hours used: {data['hours']}

            - It's mandatory to give a number in carbon footprint, do not give null or zero values in carbon footprint, just give approximate values
            - Please calculate the carbon footprint on upper limit which means give higher end values of carbon footprint not the mean values
            - Please note not to give the energy consumption values in carbon footprint, only give the carbon footprint values
            - Give tips and description in line format, do not give in list format and do not use bold or italic text

            Respond ONLY with a JSON object in this exact format:
            {{
                "carbon_footprint": <number>,
                "category": "Energy",
                "description": "<usage analysis>",
                "recommendations": "<conservation tips>"
            }}"""
        else:  
            prompt = f"""
            
            Based on the following table, calculate the carbon footprint for the given transport usage

            - Car (Petrol): 0.192 kg CO₂ per km
            - Car (Diesel): 0.171 kg CO₂ per km
            - Electric Car: 0.05 kg CO₂ per km (based on average grid emissions)
            - Hybrid Car (Petrol-Electric): 0.085 kg CO₂ per km (average, varies with usage)
            - Motorbike (Petrol): 0.103 kg CO₂ per km
            - Bus (Diesel): 0.089 kg CO₂ per km (average occupancy of 20-40 people)
            - Bus (Electric): 0.018 kg CO₂ per km (based on average grid emissions)
            - Light Truck (Diesel): 0.206 kg CO₂ per km
            - Van (Petrol): 0.227 kg CO₂ per km
            - Train (Electric): 0.041 kg CO₂ per km (based on average grid emissions)
            - Train (Diesel): 0.115 kg CO₂ per km
            - High-Speed Train (Electric): 0.025 kg CO₂ per km (higher efficiency compared to regular trains)
            - Airplane (Domestic): 0.255 kg CO₂ per km per passenger
            - Airplane (International): 0.180 kg CO₂ per km per passenger
            - Private Jet (Small): 2.5 kg CO₂ per km per passenger
            - Ferry (Diesel): 0.29 kg CO₂ per km per passenger
            - Cargo Ship (Heavy, Diesel): 0.010 kg CO₂ per ton per km
            - Container Ship (Large): 0.030 kg CO₂ per ton per km
            - Yacht (Motorized): 0.1–0.5 kg CO₂ per km
            - Bicycle: 0 kg CO₂ per km
            - E-Scooter: 0.017 kg CO₂ per km (based on grid emissions for charging)
            - Walking: 0 kg CO₂ per km
            - Tram (Electric): 0.039 kg CO₂ per km (based on average grid emissions)
            - Tractor (Diesel): 0.290 kg CO₂ per km
            - Scooter (Petrol): 0.076 kg CO₂ per km
            - Segway: 0.02 kg CO₂ per km (based on charging emissions)
            - Horse and Cart: 0.0 kg CO₂ per km
            - Electric Bike: 0.008 kg CO₂ per km (based on grid emissions for charging)
            - Electric Bus: 0.05–0.08 kg CO₂ per km (based on grid emissions)
            - Light Commercial Van (Diesel): 0.23–0.3 kg CO₂ per km
            - Heavy Duty Truck (Diesel): 0.6 kg CO₂ per km
            
            Please analyze this transport usage and provide a JSON response, use the above table for calculation:
            Vehicle: {data['vehicle']}
            Distance: {data['distance']} km

            It's mandatory to give a number in carbon footprint, do not give null or zero values in carbon footprint, just give approximate values
            Give tips and description in line format, do not give in list format and do not use bold or italic text
            Respond ONLY with a JSON object in this exact format:
            {{
                "carbon_footprint": <number>,
                "category": "Transport",
                "description": "<trip analysis>",
                "recommendations": "<emission reduction tips>"
            }}"""

        
        response = model.generate_content(prompt)
        
        if not response.text:
            raise ValueError("Empty response from AI")

        
        result = clean_and_parse_response(response.text)
        
        
        result['date'] = datetime.now().strftime('%Y-%m-%d')
        
        return jsonify(result)

    except Exception as e:
        print(f"Error processing text: {str(e)}")  
        error_message = str(e) if str(e) != "Invalid response format from AI" else "Failed to process input"
        return jsonify({'error': error_message}), 500

@app.route('/process_offset', methods=['POST'])
def process_offset():
    try:
        image_data = request.json.get('image')
        description = request.json.get('description')
        
        if not image_data or not description:
            raise ValueError("Both image and description are required")

        
        image_data = image_data.split(',')[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(base64.b64decode(image_data))
            temp_path = temp_file.name

        combined_prompt = f"""
        Analyze this environmental activity image along with the provided description and provide the following information in JSON format:
        
        Activity Description: {description}
        
        1. Carbon offset in KG CO2 (mandatory to give a number approx., should be negative)
        2. Category should be "Offset"
        3. Description of the environmental activity (incorporate the provided description)
        4. AI tips for maximizing impact
        5. Give tips and description in line format, do not give in list format and do not use bold or italic text

        Format:
        {{
            "carbon_footprint": negative number,
            "category": "Offset",
            "description": string,
            "recommendations": string
        }}
        """

        image_file = genai.upload_file(path=temp_path)
        response = model.generate_content([image_file, combined_prompt])
        
        os.unlink(temp_path)

        if not response.text:
            raise ValueError("Empty response from AI")

        result = clean_and_parse_response(response.text)
        result['date'] = datetime.now().strftime('%Y-%m-%d')
        
        return jsonify(result)

    except Exception as e:
        print(f"Error processing offset data: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
