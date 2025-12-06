const axios = require('axios');

async function test() {
    try {
        const res = await axios.post('https://lex-api.victoriousdesert-f8e685e0.uksouth.azurecontainerapps.io/legislation/search', {
            query: 'computer misuse',
            limit: 1
        });
        console.log(JSON.stringify(res.data, null, 2));
    } catch (e) {
        console.error(e);
    }
}

test();
