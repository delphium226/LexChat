const nodemailer = require('nodemailer');
const config = require('../config');

// Create reusable transporter object using the default SMTP transport
const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
        user: config.email.user,
        pass: config.email.pass
    }
});

const sendWelcomeEmail = async (to, username, password) => {
    if (!config.email.user || !config.email.pass) {
        console.warn('Email credentials not configured. Skipping welcome email.');
        return;
    }

    const mailOptions = {
        from: config.email.user,
        to: to,
        subject: 'Welcome to LexChat UK',
        html: `
            <h3>Welcome to LexChat UK!</h3>
            <p>Your account has been created successfully.</p>
            <p><strong>Username:</strong> ${username}</p>
            <p><strong>Password:</strong> ${password}</p>
            <p>Please log in and change your password immediately.</p>
            <br>
            <p>Best regards,<br>The LexChat Team</p>
        `
    };

    try {
        await transporter.sendMail(mailOptions);
        console.log(`Welcome email sent to ${to}`);
    } catch (error) {
        console.error('Error sending welcome email:', error);
    }
};

const sendPasswordResetEmail = async (to, username, resetToken) => {
    if (!config.email.user || !config.email.pass) {
        console.warn('Email credentials not configured. Skipping reset email.');
        return;
    }

    // In a real app, this would be a link to a frontend route with the token
    const mailOptions = {
        from: config.email.user,
        to: to,
        subject: 'Password Reset Request',
        html: `
            <h3>Password Reset Request</h3>
            <p>Hello ${username},</p>
            <p>We received a request to reset your password.</p>
            <p>Since this is an internal mocked reset flow, please contact your administrator to manually reset your credentials if you cannot remember them.</p>
            <p>If you did recall your password, you can change it in the Settings page.</p>
            <br>
            <p>Best regards,<br>The LexChat Team</p>
        `
    };

    try {
        await transporter.sendMail(mailOptions);
        console.log(`Password reset email sent to ${to}`);
    } catch (error) {
        console.error('Error sending reset email:', error);
    }
};

module.exports = {
    sendWelcomeEmail,
    sendPasswordResetEmail
};
