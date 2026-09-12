/** @type {import('next').NextConfig} */
const nextConfig = {
    experimental: {
        optimizeCss: true, // Force l'optimisation CSS compatible avec Tailwind v3
        // Reçu PDF (base64) transitant par un Server Action — la limite par
        // défaut (1mb) suffit à la plupart des reçus mais pas à tous les cas.
        serverActions: {
            bodySizeLimit: '5mb',
        },
    },
};

export default nextConfig;