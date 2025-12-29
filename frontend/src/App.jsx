import { useState } from "react";
import { generate } from "./api";
import Dropzone from "./components/Dropzone";
import OptionsPanel from "./components/OptionsPanel";
import DownloadButton from "./components/DownloadButton";

export default function App() {
  const [file, setFile] = useState(null);
  const [blob, setBlob] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleGenerate(options) {
    setLoading(true);
    const result = await generate({
      image: file,
      ...options
    });
    setBlob(result);
    setLoading(false);
  }

  return (
    <div style={{ padding: 24 }}>
      <h2>Sand Art Generator</h2>

      <Dropzone onSelect={setFile} />

      {file && (
        <OptionsPanel
          disabled={loading}
          onGenerate={handleGenerate}
        />
      )}

      <DownloadButton blob={blob} />
    </div>
  );
}