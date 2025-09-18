import React from 'react';
import { cn } from '../../lib/utils';

const Button = React.forwardRef(({ className, variant, size, ...props }, ref) => (
  <button
    className={cn(
      "inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
      {
        "bg-blue-600 text-white hover:bg-blue-700": variant === "default" || !variant,
        "border border-gray-300 bg-white hover:bg-gray-50 hover:text-gray-900": variant === "outline",
        "bg-red-600 text-white hover:bg-red-700": variant === "destructive",
        "hover:bg-gray-100 hover:text-gray-900": variant === "ghost",
        "bg-gray-100 text-gray-900 hover:bg-gray-200": variant === "secondary",
      },
      {
        "h-10 px-4 py-2": size === "default" || !size,
        "h-9 rounded-md px-3": size === "sm",
        "h-11 rounded-md px-8": size === "lg",
        "h-10 w-10": size === "icon",
      },
      className
    )}
    ref={ref}
    {...props}
  />
));
Button.displayName = "Button";

export { Button };