import pandas as pd
import streamlit as st
import easyocr
import cv2
import os
import re
from sqlalchemy import create_engine
import pymysql
# CONNECTING WITH MYSQL DATABASE
mydb = pymysql.connect(
        host = "localhost",
        user = "root",
        password = "root",
        
        autocommit = True
    )
mycursor = mydb.cursor()
mycursor.execute("create database if not exists Bizcard")
mydb.commit()
mycursor.execute("use Bizcard")

# Initialize the OCR reader
reader = easyocr.Reader(['en'])

# Function to perform OCR and highlight detected text
def perform_ocr_and_highlight(image_path): 
    image = cv2.imread(image_path) # Read the image
    result = reader.readtext(image) # Perform OCR on the image
    text_list = [text for _, text, _ in result] # Extract text from the result tuples
    for detection in result:  # Draw bounding boxes around detected text
        bbox = detection[0]
        pt1 = tuple(map(int, bbox[0]))
        pt2 = tuple(map(int, bbox[2]))
        cv2.rectangle(image, pt1, pt2, (0, 255, 0), 2)
    return image, text_list
# Function to convert image to binary data
def convert_image_to_binary(image_path):
    with open(image_path, "rb") as file:
        binary_data = file.read()
    return binary_data

# Function to extract data from OCR result
def extract_data(result):
    data = {"company_name": [],
            "card_holder": [],
            "designation": [],
            "mobile_number": [],
            "email": [],
            "website": [],
            "area": [],
            "city": [],
            "state": [],
            "pin_code": [],
            }

    for ind, i in enumerate(result):

        # To get WEBSITE_URL
        if "www " in i.lower() or "www." in i.lower():
            data["website"].append(i)
        elif "WWW" in i:
            data["website"] = result[4] + "." + result[5]

        # To get EMAIL ID
        elif "@" in i:
            data["email"].append(i)

        # To get MOBILE NUMBER
        elif "-" in i:
            data["mobile_number"].append(i)
            if len(data["mobile_number"]) == 2:
                data["mobile_number"] = " & ".join(data["mobile_number"])

        # To get COMPANY NAME
        elif ind == len(result) - 1:
            data["company_name"].append(i)

        # To get CARD HOLDER NAME
        elif ind == 0:
            data["card_holder"].append(i)

        # To get DESIGNATION
        elif ind == 1:
            data["designation"].append(i)

        # To get AREA
        if re.findall('^[0-9].+, [a-zA-Z]+', i):
            data["area"].append(i.split(',')[0])
        elif re.findall('[0-9] [a-zA-Z]+', i):
            data["area"].append(i)

        # To get CITY NAME
        match1 = re.findall('.+St , ([a-zA-Z]+).+', i)
        match2 = re.findall('.+St,, ([a-zA-Z]+).+', i)
        match3 = re.findall('^[E].*', i)
        if match1:
            data["city"].append(match1[0])
        elif match2:
            data["city"].append(match2[0])
        elif match3:
            data["city"].append(match3[0])

        # To get STATE
        state_match = re.findall('[a-zA-Z]{9} +[0-9]', i)
        if state_match:
            data["state"].append(i[:9])
        elif re.findall('^[0-9].+, ([a-zA-Z]+);', i):
            data["state"].append(i.split()[-1])
        if len(data["state"]) == 2:
            data["state"].pop(0)

        # To get PINCODE
        if len(i) >= 6 and i.isdigit():
            data["pin_code"].append(i)
        elif re.findall('[a-zA-Z]{9} +[0-9]', i):
            data["pin_code"].append(i[10:])

    return data

# Function to create DataFrame
def create_dataframe(data):
    df = pd.DataFrame(data)
    return df

def upload_to_mysql(df, database_name):
    try:
        engine = create_engine(f'mysql+pymysql://root:root@localhost:3306/{database_name}')
        connection = engine.connect()
        existing_records = pd.read_sql("SELECT * FROM card_data", connection)
        unique_key_columns = ['card_holder', 'designation']
        df_to_insert = df[~df.set_index(unique_key_columns).index.isin(existing_records.set_index(unique_key_columns).index)]
        if not df_to_insert.empty:
            df_to_insert.to_sql(name='card_data', con=engine, if_exists='append', index=False)
            st.success("Uploaded to database successfully!")
        else:
            st.warning("Duplicate records detected.")
        connection.close()
    except Exception as e:
        st.error(f"Error occurred during upload to MySQL: {e}")

# Function to update business card data in the database
def update_business_card_data(selected_card, company_name, card_holder, designation, mobile_number, email,
                              website, area, city, state, pin_code):
    try:
        mycursor.execute("""UPDATE card_data SET company_name=%s, card_holder=%s, designation=%s,
                            mobile_number=%s, email=%s, website=%s, area=%s, city=%s, state=%s, pin_code=%s
                            WHERE card_holder=%s""",
                        (company_name, card_holder, designation, mobile_number, email, website,
                        area, city, state, pin_code, selected_card))
        mydb.commit()
        st.success("Information updated in database successfully.")
    except Exception as e:
        st.error(f"Error occurred while updating information: {e}")

# Function to delete business card data from the database
def delete_business_card_data(selected_card):
    try:
        mycursor.execute(f"DELETE FROM card_data WHERE card_holder='{selected_card}'")
        mydb.commit()
        st.success("Business card information deleted from database.")
    except Exception as e:
        st.error(f"Error occurred while deleting information: {e}")

# Function to display form inputs for modifying business card data
def display_modify_form(selected_card, result):
    if result:
        company_name = st.text_input("Company Name", result[0])
        card_holder = st.text_input("Card Holder", result[1])
        designation = st.text_input("Designation", result[2])
        mobile_number = st.text_input("Mobile Number", result[3])
        email = st.text_input("Email", result[4])
        website = st.text_input("Website", result[5])
        area = st.text_input("Area", result[6])
        city = st.text_input("City", result[7])
        state = st.text_input("State", result[8])
        pin_code = st.text_input("Pin Code", result[9])

        if st.button("Commit changes to DB"):
            update_business_card_data(selected_card, company_name, card_holder, designation, mobile_number, email,
                                      website, area, city, state, pin_code)
    else:
        st.warning("No data found for the selected card holder.")

# Function to display delete confirmation and delete business card data
def display_delete_confirmation(selected_card):
    st.write(f"### You have selected :green[**{selected_card}'s**] card to delete")
    st.write("#### Proceed to delete this card?")

    if st.button("Yes, Delete Business Card"):
        delete_business_card_data(selected_card)

# Main function
def main():
    st.title("Business Card Information Extractor")
    selected = st.sidebar.radio("Select", ["Home","Upload Business Card", "Modify"])
    
    if selected == "Home":
        st.write("""
        The Business Card Information Extractor is an application designed to assist users in efficiently extracting relevant information from business cards. It utilizes optical character recognition (OCR) technology to scan and interpret text from images of business cards, enabling users to digitize and organize the information for further use.
        
        Key features of the Business Card Information Extractor may include:
        
        - **Image Upload**: Users can upload images of business cards directly to the application.
        - **Text Extraction**: The application extracts text from the uploaded images using OCR.
        - **Data Organization**: Extracted information such as company name, cardholder name, contact details, etc., are organized and presented in a structured format.
        - **Data Modification**: Users may have the option to modify or update the extracted data as needed.
        - **Database Integration**: The application may integrate with a database to store and manage extracted business card information.
        - **User Interface**: A user-friendly interface allows users to interact with the application seamlessly, facilitating a smooth user experience.
        - **Efficiency**: By automating the process of extracting information from business cards, the application enhances efficiency and productivity for users dealing with a large volume of business card data.
        
        Overall, the Business Card Information Extractor simplifies the task of digitizing and managing business card information, saving time and effort while ensuring accuracy and organization.
        """)

    if selected == "Upload Business Card":
        uploaded_card = st.file_uploader("Upload here", label_visibility="collapsed", type=["png", "jpeg", "jpg"])

        if uploaded_card is not None:
            image_path = os.path.join("uploaded_cards", uploaded_card.name)
            with open(image_path, "wb") as f:
                f.write(uploaded_card.getbuffer())
            st.image(image_path, caption='Uploaded Business Card', use_column_width=True)
            highlighted_image, result = perform_ocr_and_highlight(image_path)
            st.image(highlighted_image, caption='Uploaded Business Card with Highlights', use_column_width=True)
            data = extract_data(result)
            df = create_dataframe(data)
            st.success("### Data Extracted!")
            st.write(df)
            if st.button("Upload to Database"):
                try:
                    upload_to_mysql(df, "Bizcard")
                except Exception as e:
                    st.error(f"Error: {e}")

    # MODIFY MENU    
    if selected == "Modify":
        col1, col2= st.columns([3, 3])
        col2.markdown("## Delete the data here")
        column1, column2 = st.columns(2, gap="large")
        try:
            with column1:
                mycursor.execute("SELECT card_holder FROM card_data")
                result = mycursor.fetchall()
                business_cards = {}
                for row in result:
                    business_cards[row[0]] = row[0]
                selected_card = st.selectbox("Select a card holder name to update", list(business_cards.keys()))
                st.markdown("#### Update or modify any data below")
                mycursor.execute("SELECT * FROM card_data WHERE card_holder=%s", (selected_card,))
                result = mycursor.fetchone()

                # Display modify form inputs
                display_modify_form(selected_card, result)

            with column2:
                mycursor.execute("SELECT card_holder FROM card_data")
                result = mycursor.fetchall()
                business_cards = {}
                for row in result:
                    business_cards[row[0]] = row[0]
                selected_card = st.selectbox("Select a card holder name to delete", list(business_cards.keys()))

                # Display delete confirmation
                display_delete_confirmation(selected_card)
        except Exception as e:
            st.warning(f"An error occurred: {e}")

        if st.button("View updated data"):
            mycursor.execute("SELECT * FROM card_data")
            updated_df = pd.DataFrame(mycursor.fetchall(), columns=["Company_Name", "Card_Holder", "Designation",
                                                                    "Mobile_Number", "Email", "Website", "Area",
                                                                    "City", "State", "Pin_Code"])
            st.write(updated_df)

if __name__ == "__main__":
    main()
