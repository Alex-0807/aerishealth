import { CartCount } from '../components/CartCount'
import { useCart } from '../hooks/useCart'
import { useProduct } from '../hooks/useProduct'
import { ProductDetails } from './ProductDetails'

export function ProductPage({ productId }: { productId: string }) {
  const product = useProduct(productId)
  const cart = useCart()

  return (
    <div className="page">
      <header className="site-header">
        <span className="site-header__brand">Threadline</span>
        <CartCount state={cart.state} />
      </header>

      <main id="main">
        {product.state.status === 'loading' ? (
          <p role="status" className="page-message">
            Loading product…
          </p>
        ) : product.state.status === 'error' ? (
          <div role="alert" className="page-message page-message--error">
            <p>{product.state.message}</p>
            <button type="button" onClick={product.retry}>
              Try again
            </button>
          </div>
        ) : (
          <ProductDetails
            // Remount (resetting selection) only if a different product is shown.
            key={product.state.product.id}
            product={product.state.product}
            refreshProduct={product.refresh}
            applyStock={product.applyStock}
            setCart={cart.setCart}
            refreshCart={cart.refresh}
          />
        )}
      </main>
    </div>
  )
}
