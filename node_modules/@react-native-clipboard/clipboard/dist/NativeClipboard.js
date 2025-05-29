
Object.defineProperty(exports, "__esModule", { value: true });
exports.removeAllListeners = exports.addListener = void 0;
const react_native_1 = require("react-native");
exports.default = react_native_1.TurboModuleRegistry.get('RNCClipboard');
const EVENT_NAME = 'RNCClipboard_TEXT_CHANGED';
const eventEmitter = new react_native_1.NativeEventEmitter(react_native_1.NativeModules.RNCClipboard);
let listenerCount = eventEmitter.listenerCount;
// listenerCount is only available from RN 0.64
// Older versions only have `listeners`
if (!listenerCount) {
    listenerCount = (eventType) => {
        // @ts-ignore
        return eventEmitter.listeners(eventType).length;
    };
}
else {
    listenerCount = eventEmitter.listenerCount.bind(eventEmitter);
}
const addListener = (callback) => {
    if (listenerCount(EVENT_NAME) === 0) {
        react_native_1.NativeModules.RNCClipboard.setListener();
    }
    const res = eventEmitter.addListener(EVENT_NAME, callback);
    // Path the remove call to also remove the native listener
    // if we no longer have listeners
    // @ts-ignore
    res._remove = res.remove;
    res.remove = function () {
        // @ts-ignore
        this._remove();
        if (listenerCount(EVENT_NAME) === 0) {
            react_native_1.NativeModules.RNCClipboard.removeListener();
        }
    };
    return res;
};
exports.addListener = addListener;
const removeAllListeners = () => {
    eventEmitter.removeAllListeners(EVENT_NAME);
    react_native_1.NativeModules.RNCClipboard.removeListener();
};
exports.removeAllListeners = removeAllListeners;
