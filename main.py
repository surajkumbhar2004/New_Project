from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
import pandas as pd
from fuzzywuzzy import process
import os

app = FastAPI()

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure folder exists

data_file = os.path.join(UPLOAD_DIR, "meldepCustomers.xlsx")

# Function to load and clean data
def load_data():
    if not os.path.exists(data_file):
        return None, None  # No file uploaded yet

    df = pd.read_excel(data_file)
    df.columns = df.columns.str.strip()  # Clean column names

    required_columns = {"Id", "name"}
    if not required_columns.issubset(df.columns):
        raise KeyError(f"❌ Missing columns in {data_file}! Expected: {required_columns}, Found: {set(df.columns)}")

    df["name"] = df["name"].astype(str).map(lambda x: x.strip().replace("{", "").replace("}", ""))  # Clean names
    df["Id"] = df["Id"].astype(str).map(lambda x: x.strip())  # Clean IDs

    client_dict = dict(zip(df["name"], df["Id"]))  # Fast lookup
    client_names_list = list(client_dict.keys())  # List for fuzzy matching
    return client_dict, client_names_list

# Load data initially
client_dict, client_names_list = load_data()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as buffer:
        buffer.write(await file.read())

    global client_dict, client_names_list
    client_dict, client_names_list = load_data()  # Reload data after upload
    return {"message": "File uploaded successfully"}

@app.get("/get_client_id")
def get_client_id(name: str):
    if not client_dict:
        raise HTTPException(status_code=400, detail="No data available. Please upload an Excel file first.")

    name = name.strip().replace("{", "").replace("}", "")

    if not name:
        raise HTTPException(status_code=400, detail="Please provide a valid name")

    # Exact match
    if name in client_dict:
        return {
            "id": client_dict[name],
            "name": name,
            "match_type": "Exact"
        }

    # Fuzzy matching
    best_match, score = process.extractOne(name, client_names_list)
    if score >= 80:
        return {
            "id": client_dict[best_match],
            "name": best_match,
            "match_type": "Fuzzy",
            "score": score
        }

    raise HTTPException(status_code=404, detail="No close match found")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Client ID Finder</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                text-align: center;
                margin: 0;
                padding: 0;
            }

            .container {
                width: 50%;
                margin: 50px auto;
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }

            h1 {
                color: #333;
            }

            .upload-section, .search-section {
                margin: 20px 0;
            }

            input[type="file"], input[type="text"] {
                padding: 10px;
                width: 80%;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-bottom: 10px;
            }

            button {
                background: #28a745;
                color: white;
                border: none;
                padding: 10px 15px;
                cursor: pointer;
                border-radius: 5px;
            }

            button:hover {
                background: #218838;
            }

            #result {
                margin-top: 20px;
                padding: 10px;
                background: #fff3cd;
                border: 1px solid #ffeeba;
                display: none;
            }
        </style>
    </head>
    <body>

        <div class="container">
            <h1>Client ID Finder</h1>

            <!-- File Upload Section -->
            <div class="upload-section">
                <input type="file" id="fileInput">
                <button onclick="uploadFile()">Upload</button>
            </div>

            <!-- Search Section -->
            <div class="search-section">
                <input type="text" id="nameInput" placeholder="Enter client name">
                <button onclick="searchClient()">Search</button>
            </div>

            <!-- Display Result -->
            <div id="result"></div>
        </div>

        <script>
            function uploadFile() {
                let fileInput = document.getElementById("fileInput");
                if (!fileInput.files.length) {
                    alert("Please select a file!");
                    return;
                }

                let formData = new FormData();
                formData.append("file", fileInput.files[0]);

                fetch("/upload", {
                    method: "POST",
                    body: formData,
                })
                .then(response => response.json())
                .then(data => alert("File uploaded successfully!"))
                .catch(error => alert("Error uploading file"));
            }

            function searchClient() {
                let name = document.getElementById("nameInput").value.trim();
                if (!name) {
                    alert("Please enter a name!");
                    return;
                }

                fetch(`/get_client_id?name=${encodeURIComponent(name)}`)
                .then(response => {
                    if (!response.ok) throw new Error("No match found");
                    return response.json();
                })
                .then(data => {
                    let resultDiv = document.getElementById("result");
                    resultDiv.innerHTML = `
                        <p><strong>ID:</strong> ${data.id}</p>
                        <p><strong>Name:</strong> ${data.name}</p>
                        <p><strong>Match Type:</strong> ${data.match_type}</p>
                        ${data.score ? `<p><strong>Score:</strong> ${data.score}</p>` : ""}
                    `;
                    resultDiv.style.display = "block";
                })
                .catch(error => {
                    document.getElementById("result").innerHTML = "<p>No match found</p>";
                });
            }
        </script>

    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
