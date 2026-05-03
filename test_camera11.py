import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image, ImageGrab  
import numpy as np
from torchvision.models import vit_b_16
import tkinter as tk
from tkinter import messagebox
from tkinter import font as tkfont
import os
import time

# --- Cloud SDKs ---
import firebase_admin
from firebase_admin import credentials, firestore
import cloudinary
import cloudinary.uploader


# ==========================================
# 1. CLOUD INITIALIZATION
# ==========================================

# --- FIREBASE ---
try:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Database connected successfully!")
except Exception as e:
    print(f"❌ Firebase setup failed. Check your JSON key: {e}")

# --- CLOUDINARY ---
# TODO: Replace these with your actual keys from the Cloudinary Dashboard
cloudinary.config( 
  cloud_name = "dxmd685vr", 
  api_key = "228849167966948", 
  api_secret = "u8LBOu7lEn97TP6KNQ7bkITiugA",
  secure = True
)


# ==========================================
# 2. AI MODEL SETUP
# ==========================================
def load_model(weights_path):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading model on: {device}")
    
    model = vit_b_16() 
    model.heads.head = nn.Sequential(
        nn.BatchNorm1d(768),
        nn.Dropout(0.5),       
        nn.Linear(768, 7)      
    )
    
    try:
        model.load_state_dict(torch.load(weights_path, map_location=device))
        print("✅ Model weights loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model weights: {e}")
        
    model.eval()      
    model.to(device)  
    return model, device


# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def get_diagnosis_sentence(dimension, score):
    if score < 40.0:
        return f"Low levels: Based on your facial scanning, there were only mild signs of {dimension} and it's up to you if you want to schedule for a consultation."
    elif score < 65.0:
        return f"Slight level increase: Based on your facial scanning, there were slight elevations of {dimension} and we encourage you to look after yourself and/or schedule for a consultation."
    else:
        return f"Increased levels: Based on your facial scanning, there were high elevations of {dimension} and we recommend that you ask a professional for guidance."


# ==========================================
# 4. CLOUDINARY & FIREBASE SAVING LOGIC 
# ==========================================
def save_to_database(email, dep, anx, str_score, frame, window, crop_y):
    if not email or "@" not in email:
        messagebox.showwarning("Invalid Input", "Please enter a valid email address.")
        return

    # --- 1. LOCAL BACKUP (Safety net for defense) ---
    save_dir = "snapshots"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    timestamp = int(time.time())

    face_filename = f"face_{timestamp}.jpg"
    face_path = os.path.join(save_dir, face_filename)
    cv2.imwrite(face_path, frame)

    result_filename = f"result_{timestamp}.jpg"
    result_path = os.path.join(save_dir, result_filename)
    
    try:
        window.update()
        x = window.winfo_rootx()
        y = window.winfo_rooty()
        width = window.winfo_width() 
        y_bottom_abs = y + crop_y
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y_bottom_abs))
        screenshot.save(result_path)
    except Exception as e:
        print(f"Screenshot Error: {e}")
        result_filename = None 

    # --- 2. UPLOAD TO CLOUDINARY ---
    face_url = None
    result_url = None
    
    try:
        # Upload Face
        face_response = cloudinary.uploader.upload(face_path, folder="thesis_faces")
        face_url = face_response['secure_url']
        
        # Upload Result (if capture didn't fail)
        if result_filename:
            result_response = cloudinary.uploader.upload(result_path, folder="thesis_results")
            result_url = result_response['secure_url']
            
    except Exception as e:
        messagebox.showerror("Cloudinary Error", f"Failed to upload images to the cloud: {e}")
        return # Stop execution if image upload fails

    # --- 3. SAVE DATA AND URLS TO FIREBASE ---
    try:
        doc_ref = db.collection('assessment_results').document()
        doc_ref.set({
            'email': email,
            'depression': float(dep),
            'anxiety': float(anx),
            'stress': float(str_score),
            'face_image_url': face_url,
            'result_image_url': result_url if result_url else "capture_failed", 
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        messagebox.showinfo("Cloud Sync Complete", "Data securely saved to Firebase!\nImages successfully hosted on Cloudinary.")
        window.destroy()

    except Exception as e:
        messagebox.showerror("Firebase Error", f"Failed to upload data to Firestore: {e}")


# ==========================================
# 5. USER INTERFACE (TKINTER) - RPi Optimized
# ==========================================
def show_results_ui(dep_score, anx_score, str_score, captured_frame):
    root = tk.Tk()
    root.title("Facial Scanning Report")
    root.geometry("650x480") # Shrunk window height to fit Pi screen perfectly
    root.configure(bg="#FFFFFF") 

    title_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
    header_font = tkfont.Font(family="Helvetica", size=10, weight="bold")
    body_font = tkfont.Font(family="Helvetica", size=10)
    
    text_dark = "#2C3E50"  
    bg_gray = "#F8F9F9"    

    # --- 1. NOTICE MOVED TO THE TOP ---
    notice_statement = "NOTICE: This is just an initial assessment using facial scanning technology and is not a clinical diagnosis."
    notice_label = tk.Label(root, text=notice_statement, font=tkfont.Font(family="Helvetica", size=9, slant="italic"), bg="#FFFFFF", fg="#E67E22")
    notice_label.pack(pady=(10, 0))

    tk.Label(root, text="Initial Assessment Results", font=title_font, bg="#FFFFFF", fg=text_dark).pack(pady=(10, 5))

    # --- 2. DYNAMIC TEXT GENERATION LOGIC ---
    slight_list = []
    increased_list = []

    # NEW THRESHOLDS: Low (< 36.0), Slight (36.0 to 70.9), Increased (>= 71.0)
    if 36.0 <= dep_score < 71.0: slight_list.append("depression")
    elif dep_score >= 71.0: increased_list.append("depression")

    if 36.0 <= anx_score < 71.0: slight_list.append("anxiety")
    elif anx_score >= 71.0: increased_list.append("anxiety")

    if 36.0 <= str_score < 71.0: slight_list.append("stress")
    elif str_score >= 71.0: increased_list.append("stress")

    def format_list(items):
        if not items: return ""
        if len(items) == 1: return items[0]
        if len(items) == 2: return f"{items[0]} and {items[1]}"
        return f"{items[0]}, {items[1]}, and {items[2]}"

    if increased_list:
        all_elevated = format_list(slight_list + increased_list)
        main_text = (
            f"Based on your facial scan, the results indicate patterns consistent with what is commonly described as {all_elevated}.\n\n"
            "Our role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\n"
            "We recommend you schedule a consultation with a licensed mental health specialist (like a therapist, counselor, or doctor). This is a completely normal and positive step. A specialist can confirm your symptoms, offer a proper diagnosis, and create a personalized plan to help you feel your best.\n\n"
            "Remember: Symptoms are manageable, and seeking professional help is the most effective way to start feeling better."
        )
    elif slight_list:
        slight_str = format_list(slight_list)
        main_text = (
            f"Based on your facial scan, the results indicate mild patterns that may be associated with early or slight signs of {slight_str}. These indicators are not necessarily a cause for concern but may suggest that you are experiencing some emotional strain.\n\n"
            "Our role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\n"
            "At this stage, you may benefit from simple self-care practices such as taking breaks, getting enough sleep, and managing daily stress. While not required, you might also consider speaking with a licensed mental health professional for additional guidance, especially if these feelings persist or become more noticeable over time.\n\n"
            "Remember: Early awareness is valuable, and taking small steps to care for your mental health can make a meaningful difference."
        )
    else:
        main_text = (
            "Based on your facial scan, there are little to no significant patterns that suggest noticeable levels of anxiety, depression, or stress at this time. Your results appear within a typical or balanced range.\n\n"
            "Our role is to provide an initial assessment only. We are not a substitute for professional medical or mental health care.\n\n"
            "Even so, it is still important to maintain good mental well-being. Practicing healthy habits such as proper rest, regular physical activity, and staying connected with others can help you continue feeling your best. If you ever notice changes in how you feel, seeking guidance from a licensed mental health professional is always a helpful and proactive step.\n\n"
            "Remember: Maintaining mental wellness is an ongoing process, and staying mindful of your well-being is a positive step forward."
        )

    # --- 3. DISPLAY THE PARAGRAPH ---
    text_frame = tk.Frame(root, bg=bg_gray, padx=15, pady=15, relief=tk.FLAT, borderwidth=1)
    text_frame.pack(fill=tk.X, expand=False, padx=30, pady=10) # Set to fill=tk.X so it hugs the text tightly

    message_label = tk.Label(text_frame, text=main_text, font=body_font, bg=bg_gray, fg=text_dark, wraplength=560, justify=tk.LEFT)
    message_label.pack(anchor="w")

    # --- 4. SAVE TO CLOUD UI ---
    save_frame = tk.Frame(root, bg="#FFFFFF")
    save_frame.pack(pady=5)

    tk.Label(save_frame, text="Enter email to save results and snapshots to database:", font=body_font, bg="#FFFFFF", fg=text_dark).pack()
    
    email_entry = tk.Entry(save_frame, width=40, font=body_font, bg="#ECF0F1", relief=tk.FLAT)
    email_entry.pack(pady=5, ipady=3) 

    # We update root and calculate crop_y_bottom BEFORE rendering the test scores
    # This ensures the test scores aren't accidentally captured in the screenshot!
    root.update()
    crop_y_bottom = text_frame.winfo_y() + text_frame.winfo_height()

    submit_btn = tk.Button(save_frame, text="Save to Cloud", font=header_font, bg="#3498DB", fg="white", 
                           activebackground="#2980B9", activeforeground="white", relief=tk.FLAT, padx=15, pady=2,
                           command=lambda: save_to_database(email_entry.get(), dep_score, anx_score, str_score, captured_frame, root, crop_y_bottom))
    submit_btn.pack()

    # --- 5. TEMPORARY TESTING SCORES DISPLAY (MOVED TO BOTTOM) ---
    test_frame = tk.Frame(root, bg="#E8DAEF", padx=10, pady=5, relief=tk.FLAT, borderwidth=1)
    test_frame.pack(fill=tk.X, padx=30, pady=(20, 10)) # Added 20px padding to the top so it doesn't touch the submit button
    tk.Label(test_frame, text="[TESTING VIEW - RAW SCORES]", font=header_font, bg="#E8DAEF", fg="#8E44AD").pack()
    tk.Label(test_frame, text=f"Depression: {dep_score:.1f}%  |  Anxiety: {anx_score:.1f}%  |  Stress: {str_score:.1f}%", 
             font=tkfont.Font(family="Helvetica", size=9, weight="bold"), bg="#E8DAEF", fg=text_dark).pack()

    root.mainloop()

# ==========================================
# 6. MAIN CAMERA LOOP
# ==========================================
def main():
    model_path = 'student_emotion_resnet34_best.pth' 
    model, device = load_model(model_path)

    transform = transforms.Compose([
        transforms.Resize((224, 224)), 
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) 
    ])

    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)

    cap = cv2.VideoCapture(0)
    
    print("\n========================================")
    print(" THESIS CAMERA ACTIVE")
    print(" - Press SPACEBAR to capture and analyze")
    print(" - Press 'q' to quit")
    print("========================================\n")

    while True:
        ret, frame = cap.read()
        if not ret: 
            print("Failed to grab frame. Exiting...")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
        
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 2)
            cv2.putText(frame, "Press SPACE to Scan", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow('Thesis Camera', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'): 
            break
        elif key == 32: 
            gray_cap = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces_cap = face_cascade.detectMultiScale(gray_cap, scaleFactor=1.3, minNeighbors=5)

            if len(faces_cap) > 0:
                clean_frame = frame.copy() 

                x, y, w, h = faces_cap[0] 
                
                face_crop = frame[y:y+h, x:x+w]
                face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(face_rgb)

                input_tensor = transform(pil_img).unsqueeze(0).to(device)

                with torch.no_grad(): 
                    output = model(input_tensor)
                    probabilities = F.softmax(output, dim=1)[0] 

                scores = probabilities.cpu().numpy() * 100

                # ==========================================
                # EMPIRICALLY CALIBRATED RATIOS (Based on Confusion Matrix)
                # ==========================================
                # scores array: 0=Anger, 1=Disgust, 2=Fear, 3=Happiness, 4=Sadness, 5=Surprise, 6=Neutral

                # 1. Depression: Compensating for the 15-16% Sad/Neutral cross-bleed
                raw_dep = (scores[4] * 0.60) + (scores[6] * 0.40)  

                # 2. Anxiety: Compensating for low Fear accuracy (46%) by leveraging Surprise
                raw_anx = (scores[2] * 0.60) + (scores[5] * 0.40)  

                # 3. Stress: Anchoring the metric on highly accurate Disgust (92%)
                raw_str = (scores[0] * 0.50) + (scores[1] * 0.50)  

                # Keep the multipliers at 1.0 since the weighted average is already mathematically capped at 100%
                dep_score = min(raw_dep * 1.0, 100.0)
                anx_score = min(raw_anx * 1.0, 100.0)
                str_score = min(raw_str * 1.0, 100.0)

                # Pass only the raw scores; the UI function will now handle text generation
                show_results_ui(dep_score, anx_score, str_score, clean_frame)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()