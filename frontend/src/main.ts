import { createApp } from "vue";
import TDesign from "tdesign-vue-next";
import "tdesign-vue-next/es/style/index.css";
import "./styles.css";
import "./mobile.css";
import App from "./App.vue";

createApp(App).use(TDesign).mount("#app");

if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js", { scope: "/" });
  });
}
