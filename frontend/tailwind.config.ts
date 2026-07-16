    import type { Config } from "tailwindcss";
    import tailwindcssAnimate from "tailwindcss-animate";

    const config: Config = {
        darkMode: ["class"],
        content: [
            "./pages/**/*.{ts,tsx}",
            "./components/**/*.{ts,tsx}",
            "./app/**/*.{ts,tsx}",
            "./src/**/*.{ts,tsx}",
            "./constants/**/*.{ts,tsx}",
        ],
        theme: {
            container: {
                center: true,
                padding: "2rem",
                screens: {
                    "2xl": "1400px",
                },
            },
            extend: {
                colors: {
                    border: "hsl(var(--border))",
                    input: "hsl(var(--input))",
                    ring: "hsl(var(--ring))",
                    background: "hsl(var(--background))",
                    foreground: "hsl(var(--foreground))",
                    primary: {
                        DEFAULT: "hsl(var(--primary))",
                        foreground: "hsl(var(--primary-foreground))",
                    },
                    secondary: {
                        DEFAULT: "hsl(var(--secondary))",
                        foreground: "hsl(var(--secondary-foreground))",
                    },
                    destructive: {
                        DEFAULT: "hsl(var(--destructive))",
                        foreground: "hsl(var(--destructive-foreground))",
                    },
                    muted: {
                        DEFAULT: "hsl(var(--muted))",
                        foreground: "hsl(var(--muted-foreground))",
                    },
                    accent: {
                        DEFAULT: "hsl(var(--accent))",
                        foreground: "hsl(var(--accent-foreground))",
                    },
                    popover: {
                        DEFAULT: "hsl(var(--popover))",
                        foreground: "hsl(var(--popover-foreground))",
                    },
                    card: {
                        DEFAULT: "hsl(var(--card))",
                        foreground: "hsl(var(--card-foreground))",
                    },
                    fill: { 1: "rgba(255, 255, 255, 0.10)" },
                    bankGradient: "#0179FE",
                    indigo: { 500: "#6172F3", 700: "#3538CD" },
                    success: { 25: "#F6FEF9", 50: "#ECFDF3", 100: "#D1FADF", 600: "#039855", 700: "#027A48", 900: "#054F31" },
                    pink: { 25: "#FEF6FB", 100: "#FCE7F6", 500: "#EE46BC", 600: "#DD2590", 700: "#C11574", 900: "#851651" },
                    blue: { 25: "#F5FAFF", 100: "#D1E9FF", 500: "#2E90FA", 600: "#1570EF", 700: "#175CD3", 900: "#194185" },
                    sky: { 1: "#F3F9FF" },
                    black: { 1: "#00214F", 2: "#344054" },
                    gray: { 25: "#FCFCFD", 200: "#EAECF0", 300: "#D0D5DD", 500: "#667085", 600: "#475467", 700: "#344054", 900: "#101828" },
                },
                borderRadius: {
                    lg: "var(--radius)",
                    md: "calc(var(--radius) - 2px)",
                    sm: "calc(var(--radius) - 4px)",
                },
                fontSize: {
                    "10": ["10px", "14px"],
                    "11": ["11px", "16px"],
                    "12": ["12px", "16px"],
                    // Refonte frontend (partie 2/4) — "13" manquait de la palette alors
                    // que "text-13" est déjà utilisé dans une quinzaine de fichiers
                    // existants (jamais stylé jusqu'ici, faute de token défini) : ajout
                    // purement additif, corrige ces usages sans rien changer d'autre.
                    "13": ["13px", "18px"],
                    "14": ["14px", "20px"],
                    "16": ["16px", "24px"],
                    "18": ["18px", "22px"],
                    "20": ["20px", "24px"],
                    "24": ["24px", "30px"],
                    "26": ["26px", "32px"],
                    "30": ["30px", "38px"],
                    "36": ["36px", "44px"],
                },
                backgroundImage: {
                    "bank-gradient": "linear-gradient(90deg, #0179FE 0%, #4893FF 100%)",
                    "gradient-mesh": "url('/icons/gradient-mesh.svg')",
                    "bank-green-gradient": "linear-gradient(90deg, #01797A 0%, #489399 100%)",
                },
                boxShadow: {
                    form: "0px 1px 2px 0px rgba(16, 24, 40, 0.05)",
                    chart: "0px 1px 3px 0px rgba(16, 24, 40, 0.10), 0px 1px 2px 0px rgba(16, 24, 40, 0.06)",
                    profile: "0px 12px 16px -4px rgba(16, 24, 40, 0.08), 0px 4px 6px -2px rgba(16, 24, 40, 0.03)",
                    creditCard: "8px 10px 16px 0px rgba(0, 0, 0, 0.05)",
                },
                fontFamily: {
                    inter: "var(--font-inter)",
                    "ibm-plex-serif": "var(--font-ibm-plex-serif)",
                    // Refonte frontend (partie 1/4) — font-heading (titres) et font-mono
                    // (montants/chiffres/timestamps, tabular-nums) : voir app/layout.tsx.
                    // font-mono remplace volontairement la pile monospace système par
                    // défaut de Tailwind : déjà utilisé pour les hash on-chain (font-mono
                    // existant dans TransferTimeline etc.), qui bénéficient donc aussi du
                    // registre "financier fiable" sans changement de leur code.
                    heading: ["var(--font-plus-jakarta-sans)", "sans-serif"],
                    mono: ["var(--font-ibm-plex-mono)", "monospace"],
                },
                letterSpacing: {
                    heading: "-0.01em",
                },
                keyframes: {
                    "accordion-down": {
                        from: { height: "0" },
                        to: { height: "var(--radix-accordion-content-height)" },
                    },
                    "accordion-up": {
                        from: { height: "var(--radix-accordion-content-height)" },
                        to: { height: "0" },
                    },
                    // KRYP-27 — pulsation douce de l'étape active de la timeline.
                    "timeline-pulse": {
                        "0%, 100%": { opacity: "1" },
                        "50%": { opacity: "0.35" },
                    },
                    // Refonte frontend (partie 1/4) — pointillés défilants du segment
                    // parcouru de TransferRouteIndicator (mode actif uniquement).
                    "route-dash": {
                        to: { strokeDashoffset: "-14" },
                    },
                },
                animation: {
                    "accordion-down": "accordion-down 0.2s ease-out",
                    "accordion-up": "accordion-up 0.2s ease-out",
                    "timeline-pulse": "timeline-pulse 1.6s ease-in-out infinite",
                    "route-dash": "route-dash 900ms linear infinite",
                },
            },
        },
        // Correctif shadcn/ui (vraie intégration Radix) — Dialog/Sheet/DropdownMenu/
        // Tooltip animent leur ouverture/fermeture via les classes data-[state=open]:
        // animate-in / fade-in-0 / zoom-in-95 etc. générées par ce plugin. Sans lui,
        // ces transitions ne produisaient AUCUNE animation (classes inexistantes).
        plugins: [tailwindcssAnimate],
    };

    export default config;