interface Props {
  imageUrl: string
  alt: string
}

export function ProductGallery({ imageUrl, alt }: Props) {
  return (
    <div className="gallery">
      {/* key forces a fresh <img> so the previous variant's image never lingers while the new one loads */}
      <img key={imageUrl} src={imageUrl} alt={alt} width={400} height={400} />
    </div>
  )
}
