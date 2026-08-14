import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-semibold transition disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-ink px-4 py-2.5 text-white hover:bg-moss",
        secondary: "border border-black/10 bg-white px-4 py-2.5 text-ink hover:border-moss/40 hover:bg-mint/50",
        ghost: "px-3 py-2 text-ink/65 hover:bg-black/5 hover:text-ink",
        danger: "bg-red-600 px-4 py-2.5 text-white hover:bg-red-700",
      },
      size: { default: "h-10", sm: "h-8 text-xs", lg: "h-12 px-6" },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
