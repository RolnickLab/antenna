const { createProxyMiddleware } = require('http-proxy-middleware')

module.exports = function (app) {
  app.use(
    '/api',
    createProxyMiddleware({
      // target: 'https://api.dev.insectai.org',
      target: 'http://localhost:8000',
      changeOrigin: true,
    })
  )
  app.use(
    '/nominatim',
    createProxyMiddleware({
      target: 'https://nominatim.openstreetmap.org/search',
      changeOrigin: true,
    })
  )
}
