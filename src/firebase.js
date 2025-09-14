// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyA0Yz_D8oUgHFrqkRDPw7cT4Iyk308N5SE",
    authDomain: "content-finder-4bf70.firebaseapp.com",
    projectId: "content-finder-4bf70",
    storageBucket: "content-finder-4bf70.firebasestorage.app",
    messagingSenderId: "876183474891",
    appId: "1:876183474891:web:659891a1d509dd55ee014e"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize services
export const auth = getAuth(app);
export const db = getFirestore(app);
export { app };