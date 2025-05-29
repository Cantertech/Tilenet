"use strict";
/**
 * useClipboard.ts
 * This code is inspired from the @react-native-community/hooks package
 * All credit goes to author of the useClipboard custom hooks.
 * https://github.com/react-native-community/hooks
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useClipboard = void 0;
const react_1 = require("react");
const Clipboard_1 = require("./Clipboard");
const listeners = new Set();
function setString(content) {
    Clipboard_1.Clipboard.setString(content);
    for (const listener of listeners) {
        listener(content);
    }
}
const useClipboard = () => {
    const [data, updateClipboardData] = (0, react_1.useState)("");
    (0, react_1.useEffect)(() => {
        Clipboard_1.Clipboard.getString().then(updateClipboardData);
    }, []);
    (0, react_1.useEffect)(() => {
        listeners.add(updateClipboardData);
        return () => {
            listeners.delete(updateClipboardData);
        };
    }, []);
    return [data, setString];
};
exports.useClipboard = useClipboard;
