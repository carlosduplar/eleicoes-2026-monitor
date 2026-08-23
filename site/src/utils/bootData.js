let store = null;

export function setBootData(data) {
  store = data || null;
}

export function getInitialData(filename) {
  if (!store || !(filename in store)) {
    return undefined;
  }
  return store[filename];
}

export function getBootData() {
  return store;
}
