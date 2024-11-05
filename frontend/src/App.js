import React, { useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [image, setImage] = useState(null);
  const [description, setDescription] = useState("");
  const [audioUrl, setAudioUrl] = useState("");

  const handleImageUpload = (event) => {
    setImage(event.target.files[0]);
  };

  const handleSubmit = async () => {
    const formData = new FormData();
    formData.append("file", image);

    try {
      const response = await axios.post(
        `${process.env.REACT_APP_BACKEND_URL}/describe-image/`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      setDescription(response.data.description);
      // Update audio URL with a timestamp to prevent caching
      setAudioUrl(`http://localhost:8001/audio/description_audio.mp3?timestamp=${new Date().getTime()}`);
    } catch (error) {
      console.error("Error:", error);
    }
  };

  return (
    <div className="App">
      <h1>Visual Search Assistant</h1>
      <input type="file" onChange={handleImageUpload} />
      <button onClick={handleSubmit}>Analyze Image</button>
      {description && <p>Description: {description}</p>}
      {audioUrl && (
        <div>
          <audio controls src={audioUrl} key={audioUrl} onLoad={() => setAudioUrl(audioUrl)}>
            <source src={audioUrl} type="audio/mp3" />
          </audio>
        </div>
      )}
    </div>
  );
}

export default App;
