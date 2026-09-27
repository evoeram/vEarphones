
send('Script loaded');
try {
    if (typeof Java !== 'undefined') {
        send('Java available: ' + Java.available);
    } else {
        send('Java UNDEFINED - no Java bridge in Frida 17');
    }
} catch(e) {
    send('Error: ' + e);
}
