import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ProductPage } from './pages/ProductPage'
import './styles.css'

const DEFAULT_PRODUCT_ID = 'classic-tee'
const productId = new URLSearchParams(window.location.search).get('product') ?? DEFAULT_PRODUCT_ID

const root = document.getElementById('root')
if (!root) throw new Error('#root element missing')

createRoot(root).render(
  <StrictMode>
    <ProductPage productId={productId} />
  </StrictMode>,
)
