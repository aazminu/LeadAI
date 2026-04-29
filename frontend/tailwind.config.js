/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#515152",
        graphite: "#171719",
        paper: "#F3F7FF",
        frost: "#EAF2FF",
        moss: "#6F3CFF",
        spruce: "#7437F5",
        steel: "#6F8FCC",
        coral: "#FF5B44",
        marigold: "#8B5CF6",
        pantone: "#00A651",
      },
      boxShadow: {
        panel: "0 18px 44px rgba(53, 68, 105, 0.10)",
      },
    },
  },
  plugins: [],
};
