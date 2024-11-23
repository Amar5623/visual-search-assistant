import React, { useState } from "react";
import axios from "axios";
import { useDropzone } from "react-dropzone";
import Highlighter from "react-highlight-words";
import nlp from "compromise";
import ClipLoader from "react-spinners/ClipLoader";
import "./App.css";

function App() {
  const [image, setImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [description, setDescription] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [speakerType, setSpeakerType] = useState("female");
  const [descriptionType, setDescriptionType] = useState("detailed");
  const [keywords, setKeywords] = useState([]); // Dynamic keywords for highlighting

  const onDrop = (acceptedFiles) => {
    const file = acceptedFiles[0];
    setImage(file);
    setPreviewUrl(URL.createObjectURL(file));
    setErrorMessage("");
  };

  const extractKeywords = (text) => {
    const doc = nlp(text);
    const extractedKeywords = doc.nouns().out("array");
    return extractedKeywords.slice(0, 10); // Top 10 keywords
  };

  const handleSubmit = async () => {
    if (!image) {
      setErrorMessage("Please upload an image.");
      return;
    }

    setIsLoading(true);
    setErrorMessage("");

    const formData = new FormData();
    formData.append("file", image);
    formData.append("speaker_type", speakerType);
    formData.append("description_type", descriptionType);

    try {
      const response = await axios.post(
        `${process.env.REACT_APP_BACKEND_URL}/describe-image/`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      const descriptionText = response.data.description;
      setDescription(descriptionText);
      setKeywords(extractKeywords(descriptionText));
      setAudioUrl(`${process.env.REACT_APP_BACKEND_URL}${response.data.audio_url}?timestamp=${new Date().getTime()}`);
    } catch (error) {
      setErrorMessage(
        error.response?.data?.error || "An error occurred. Please try again."
      );
      console.error("Error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1>Visual Search Assistant</h1>
        <p>Upload an image to get detailed descriptions and audio feedback!</p>
      </header>

      <div className="dropzone-container">
        <Dropzone onDrop={onDrop} />
        {image && (
          <div className="image-preview">
            <img src={previewUrl} alt="Uploaded Preview" />
            <p className="file-name">Selected File: {image.name}</p>
          </div>
        )}
      </div>

      <div className="selectors">
        <div>
          <label htmlFor="speakerType">Select Speaker Type:</label>
          <select
            id="speakerType"
            value={speakerType}
            onChange={(e) => setSpeakerType(e.target.value)}
          >
            <option value="female">Female</option>
            <option value="male">Male</option>
          </select>
        </div>

        <div>
          <label htmlFor="descriptionType">Description Type:</label>
          <select
            id="descriptionType"
            value={descriptionType}
            onChange={(e) => setDescriptionType(e.target.value)}
          >
            <option value="simplified">Simplified</option>
            <option value="detailed">Detailed</option>
          </select>
        </div>
      </div>

      <div className="action-container">
        {isLoading ? (
          <ClipLoader color="#4CAF50" size={50} />
        ) : (
          <button className="analyze-btn" onClick={handleSubmit}>
            Analyze Image
          </button>
        )}
      </div>

      {errorMessage && <p className="error">{errorMessage}</p>}

      {description && (
        <div className="description">
          <h2>Image Description:</h2>
          <p>
            <Highlighter
              highlightClassName="highlight"
              searchWords={keywords}
              autoEscape={true}
              textToHighlight={description}
            />
          </p>
        </div>
      )}

      {audioUrl && (
        <div className="audio-container">
          <audio controls src={audioUrl} key={audioUrl}>
            <source src={audioUrl} type="audio/mp3" />
          </audio>
          <a
            className="download-btn"
            href={audioUrl}
            download="description_audio.mp3"
          >
            Download Audio
          </a>
        </div>
      )}
    </div>
  );
}

const Dropzone = ({ onDrop }) => {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: "image/*",
  });

  return (
    <div {...getRootProps()} className="dropzone">
      <input {...getInputProps()} />
      {isDragActive ? (
        <p className="dropzone-text">Drop the image here...</p>
      ) : (
        <p className="dropzone-text">Drag & drop an image here, or click to upload.</p>
      )}
    </div>
  );
};

export default App;
