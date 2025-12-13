const axios = require('axios');

async function testQuery() {
    console.log('Sending test query...');
    try {
        const response = await axios.post('http://localhost:3000/api/chat', {
            model: 'mistral-large-3:675b-cloud', // Ensure this matches a valid model in config
            messages: [{ role: 'user', content: 'What is the Computer Misuse Act 1990?' }]
        }, {
            responseType: 'stream'
        });

        console.log('Response stream started...');

        const stream = response.data;
        stream.on('data', (chunk) => {
            const lines = chunk.toString().split('\n');
            lines.forEach(line => {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.substring(6);
                    try {
                        const json = JSON.parse(jsonStr);
                        if (json.type === 'token') {
                            process.stdout.write(json.content);
                        } else if (json.type === 'tool_start') {
                            console.log(`\n[TOOL START]: ${json.tool}`);
                        } else if (json.type === 'tool_end') {
                            console.log(`\n[TOOL END]: ${json.tool} (${json.result})`);
                        } else if (json.type === 'result') {
                            console.log('\n[FINAL RESULT]:', json.message.content);
                        } else if (json.type === 'error') {
                            console.error('\n[ERROR]:', json.error);
                        }
                    } catch (e) {
                        // ignore
                    }
                }
            });
        });

    } catch (error) {
        console.error('Test failed:', error.message);
    }
}

testQuery();
