from flask import Flask, render_template, request, jsonify 
'''Imports necessary modules from the Flask framework. 
Flask is used to create the web application, render_template to render HTML templates, request to handle incoming requests, 
and jsonify to convert Python dictionaries to JSON format for responses.'''
from PyPDF2 import PdfReader # Imports the PdfReader class from the PyPDF2 library, which is used to read PDF files.
from docx import Document # Imports the Document class from the docx library, which is used to read Microsoft Word (.docx) files.
import openai # Imports the openai module, which is used to interact with the OpenAI API.

app = Flask(__name__) # This line creates a Flask application instance called app.

# Set your OpenAI API key
openai.api_key = "Open API Key"

@app.route("/") # Defines a route for the root URL ("/") of the web application. When a user accesses the root URL, the index() function will be called.
def index(): # Renders the index.html template and returns it as the response to the client.
    return render_template("index.html")

# For PDF files
def generate_questions_from_pdf(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    for page_num in range(len(pdf_reader.pages)):
        yield pdf_reader.pages[page_num].extract_text()

# For docx files
def generate_questions_from_docx(docx_file):
    doc = Document(docx_file)
    for para in doc.paragraphs:
        yield para.text

def is_meaningful_text(text):
    # Check if the text contains only non-alphanumeric characters
    return any(char.isalnum() for char in text)

# This route is used to generate quiz questions based on user input.
@app.route("/api/generate_quiz", methods=["POST"])
def generate_quiz():
    text_input = request.form.get("text") # Retrieves the value of the text field from the request form.
    quiz_type = request.form.get("quiz_type") # Retrieves the value of the quiz_type field from the request form.
    num_questions = request.form.get("num_questions") # Retrieves the value of the num_questions field from the request form.

    # Check if text_input is empty and no files are uploaded
    if not text_input and "files[]" not in request.files:
        return jsonify({"error": "Text input or file upload is required. Please enter some text or upload a file."})

    # Check if num_questions is empty or None
    if not num_questions:
        return jsonify({"error": "Number of questions is required. Please enter a valid number."})

    num_questions = int(num_questions) # Converts num_questions to an integer.

    # Calculate the total number of tokens in the input text and files
    total_tokens = len(text_input.split()) if text_input else 0
    for file in request.files.getlist("files[]"):
        total_tokens += len(file.read().split())

    # Log the total number of tokens
    app.logger.info("Total tokens in input: %d", total_tokens)

    # Check if the total number of tokens exceeds the maximum limit
    if total_tokens > 16385:
        return jsonify({"error": f"You have exceeded the maximum token limit of 16385 with {total_tokens} tokens. Please reduce the amount of text or the number of files."})

    # Initializes a list of messages with a system message.
    messages = [{"role": "system", "content": "You are a student."}]

    allowed_extensions = (".docx", ".pdf")
    files = request.files.getlist("files[]")

    # Checker if the extensions are valid
    combined_text = ""

    if text_input and is_meaningful_text(text_input):
        combined_text += "\n" + text_input
    
    for file in files:
        if not file.filename.lower().endswith(allowed_extensions):
            return jsonify({"error": f"Invalid file type. Please upload only {', '.join(allowed_extensions)} files."})

        if file.filename.endswith(".pdf"):
            text = "\n".join(generate_questions_from_pdf(file))
        elif file.filename.endswith(".docx"):
            text = "\n".join(generate_questions_from_docx(file))

        if is_meaningful_text(text):
            combined_text += "\n" + text

    # Check if combined_text is meaningful
    if not is_meaningful_text(combined_text):
        return jsonify({"error": "Please input meaningful text."})

    if quiz_type == "Multiple Choice":
        messages.append({"role": "user", "content": combined_text})
        messages.append({"role": "system", "content": f"Generate {quiz_type} quiz questions and answers for {num_questions} questions. With the format of: \nNumber. Question\n\nChoices\nChoices\nChoices\nChoices\n\nAnswer\n\nExplanation."})
    elif quiz_type == "True or False":
        messages.append({"role": "user", "content": combined_text})
        messages.append({"role": "system", "content": f"Generate {quiz_type} quiz questions and answers for {num_questions} questions. With the format of: \nNumber. Question\n\nAnswer\n\nExplanation."})    
    elif quiz_type == "Fill in the Blanks":
        messages.append({"role": "user", "content": combined_text})
        messages.append({"role": "system", "content": f"Generate {quiz_type} quiz questions and answers for {num_questions} questions. With the format of: \nNumber. Question\n\nAnswer\n\nExplanation. Note: Always put a blank in the question"})
    elif quiz_type == "Identification":
        messages.append({"role": "user", "content": combined_text})
        messages.append({"role": "system", "content": f"Generate {quiz_type} quiz questions with terminology/noun short answers only for {num_questions} questions. With the format of: Description/Question\n\nAnswer."})
    else:
         return jsonify({"error": "No quiz type question..."})

    # Sends a request to the OpenAI API to generate quiz questions based on the messages list.
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=4096
        )
    # Extracts the generated questions and answers from the API response.
        questions_with_answers = response["choices"][0]["message"]["content"].strip()

        return jsonify({"questions_with_answers": questions_with_answers})
    except Exception as e:
        app.logger.error("Failed to generate questions and answers: %s", str(e))
        return jsonify({"error": "Failed to generate questions and answers. Please try again."})

# Checks if the script is being run directly then runs the Flask app
if __name__ == '__main__':
    app.run(debug=True)