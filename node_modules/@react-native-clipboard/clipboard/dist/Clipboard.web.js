"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Clipboard = void 0;
exports.Clipboard = {
    getString() {
        if (navigator === null || navigator === void 0 ? void 0 : navigator.clipboard) {
            return navigator.clipboard.readText();
        }
        const el = document.createElement("textarea");
        document.body.appendChild(el);
        el.select();
        document.execCommand("paste");
        const value = el.innerText;
        document.body.removeChild(el);
        return Promise.resolve(value);
    },
    setString(content) {
        if (navigator === null || navigator === void 0 ? void 0 : navigator.clipboard) {
            navigator.clipboard.writeText(content);
        }
        else {
            const el = document.createElement("textarea");
            el.value = content;
            document.body.appendChild(el);
            el.select();
            document.execCommand("copy");
            document.body.removeChild(el);
        }
    },
};
