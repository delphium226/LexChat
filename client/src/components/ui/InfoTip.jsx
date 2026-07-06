import React from 'react';

const InfoTip = ({ text }) => (
    <span
        title={text}
        className="ml-1 inline-block text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-help text-xs select-none leading-none"
        aria-label={text}
    >ⓘ</span>
);

export default InfoTip;
