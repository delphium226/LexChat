import React from 'react';

const InfoTip = ({ text }) => (
    <span
        title={text}
        className="ml-1 inline-block text-ink-400 hover:text-ink-600 cursor-help text-xs select-none leading-none"
        aria-label={text}
    >ⓘ</span>
);

export default InfoTip;
