export default function DownloadButton({ blob }) {
  if (!blob) return null;

  const url = URL.createObjectURL(blob);

  return (
    <a href={url} download="model.stl">
      Download STL
    </a>
  );
}